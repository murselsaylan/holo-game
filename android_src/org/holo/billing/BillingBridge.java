package org.holo.billing;

import android.app.Activity;

import com.android.billingclient.api.AcknowledgePurchaseParams;
import com.android.billingclient.api.BillingClient;
import com.android.billingclient.api.BillingClientStateListener;
import com.android.billingclient.api.BillingFlowParams;
import com.android.billingclient.api.BillingResult;
import com.android.billingclient.api.ConsumeParams;
import com.android.billingclient.api.PendingPurchasesParams;
import com.android.billingclient.api.ProductDetails;
import com.android.billingclient.api.Purchase;
import com.android.billingclient.api.PurchasesUpdatedListener;
import com.android.billingclient.api.QueryProductDetailsParams;
import com.android.billingclient.api.QueryPurchasesParams;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;

/**
 * Thin Google Play Billing bridge used from Python through pyjnius (see shop.py -> AndroidBilling).
 *
 * Written for Play Billing Library 8.x (required for new apps / updates since 31 Aug 2026). It has NOT been compiled or
 * run by the author: build an AAB, upload it to a Play Console internal-testing track and test with a license-tester
 * account before relying on it.
 *
 * Products (create them in the Play Console with exactly these ids, all "in-app products"):
 *   skin_<skin_id>                  the 15 Legendary skins: non-consumable (acknowledged, restored from ownedProducts())
 *   pack_100 pack_350 pack_1000 pack_2500   consumable diamond packs (consumed right after purchase)
 *
 * Purchases are NOT consumed / acknowledged here when they arrive: the game first sends the purchase token to the HOLO
 * server, which checks it with Google and credits the account exactly once; only then Python calls finish(token).
 * If anything breaks in between (app killed, no internet), Play keeps the purchase unfinished, refresh() reports it again
 * on the next start and the server's once-per-token rule makes the retry safe. Nothing is lost, nothing is paid twice.
 *
 * Python polls pollResult():
 *   "BUY|<product>|<token>|<orderId>"   paid - deliver it through the server, then call finish(token)
 *   "PENDING|<product>"                 payment still pending (cash / slow methods); arrives as BUY once paid
 *   "DONE|<token>|OK" / "DONE|<token>|FAIL"   finish() result
 *   "<product>:FAIL" / "_:FAIL"         cancelled or error before paying
 */
public class BillingBridge implements PurchasesUpdatedListener {
    private static final String[] PRODUCTS = {
        "skin_cyber_phantom",
        "skin_supernova",
        "skin_event_horizon",
        "skin_big_bang",
        "skin_quantum_lattice",
        "skin_saturn_ring",
        "skin_galaxy_cat",
        "skin_rainbow_unicorn",
        "skin_royal_crown",
        "skin_nova_heart",
        "skin_sakura_fox",
        "skin_leviathan",
        "skin_void_walker",
        "skin_snow_leopard",
        "skin_rocket_bunny",
        "skin_diamond_prestige",          // Cosmic Diamond, the $14.99 top item
        "pack_100", "pack_350", "pack_1000", "pack_2500",
    };

    private final Activity activity;
    private final BillingClient client;
    private final Map<String, ProductDetails> details = new ConcurrentHashMap<>();
    private final ConcurrentLinkedQueue<String> results = new ConcurrentLinkedQueue<>();
    private final Map<String, Purchase> unfinished = new ConcurrentHashMap<>();   // token -> paid, not yet finished
    private volatile boolean ready = false;
    private volatile String owned = "";

    public BillingBridge(Activity activity) {
        this.activity = activity;
        this.client = BillingClient.newBuilder(activity)
                .setListener(this)
                .enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())
                .enableAutoServiceReconnection()
                .build();
        connect();
    }

    private static boolean consumable(String id) {
        return id.startsWith("pack_");
    }

    private void connect() {
        client.startConnection(new BillingClientStateListener() {
            @Override
            public void onBillingSetupFinished(BillingResult r) {
                if (r.getResponseCode() == BillingClient.BillingResponseCode.OK) {
                    ready = true;
                    loadDetails();
                    refreshPurchases();
                }
            }

            @Override
            public void onBillingServiceDisconnected() {
                ready = false;                       // enableAutoServiceReconnection() reconnects by itself
            }
        });
    }

    private void loadDetails() {
        List<QueryProductDetailsParams.Product> list = new ArrayList<>();
        for (String id : PRODUCTS) {
            list.add(QueryProductDetailsParams.Product.newBuilder().setProductId(id).setProductType(BillingClient.ProductType.INAPP).build());
        }
        client.queryProductDetailsAsync(QueryProductDetailsParams.newBuilder().setProductList(list).build(), (r, result) -> {
            if (r.getResponseCode() == BillingClient.BillingResponseCode.OK && result != null) {
                for (ProductDetails d : result.getProductDetailsList()) details.put(d.getProductId(), d);
            }
        });
    }

    /** Purchases made earlier or finished while the app was closed: every paid, unfinished one is reported again. */
    private void refreshPurchases() {
        client.queryPurchasesAsync(QueryPurchasesParams.newBuilder().setProductType(BillingClient.ProductType.INAPP).build(), (r, purchases) -> {
            StringBuilder sb = new StringBuilder();
            for (Purchase p : purchases) {
                if (p.getPurchaseState() == Purchase.PurchaseState.PURCHASED) {
                    for (String id : p.getProducts()) {
                        if (!consumable(id) && p.isAcknowledged()) {
                            if (sb.length() > 0) sb.append(',');
                            sb.append(id);
                        }
                    }
                    handle(p);
                }
            }
            owned = sb.toString();
        });
    }

    // ---- called from Python ------------------------------------------------------------------------------------
    public boolean isReady() {
        return ready;
    }

    /** The cheapest offer Play has for the product right now: a discount offer scheduled in the Play Console (a sale)
     *  shows up next to the regular one. getOneTimePurchaseOfferDetailsList() is only set when there are several. */
    private static ProductDetails.OneTimePurchaseOfferDetails cheapest(ProductDetails d) {
        List<ProductDetails.OneTimePurchaseOfferDetails> list = d.getOneTimePurchaseOfferDetailsList();
        ProductDetails.OneTimePurchaseOfferDetails best = null;
        if (list != null) {
            for (ProductDetails.OneTimePurchaseOfferDetails o : list) {
                if (best == null || o.getPriceAmountMicros() < best.getPriceAmountMicros()) best = o;
            }
        }
        return best != null ? best : d.getOneTimePurchaseOfferDetails();
    }

    private static ProductDetails.OneTimePurchaseOfferDetails dearest(ProductDetails d) {
        List<ProductDetails.OneTimePurchaseOfferDetails> list = d.getOneTimePurchaseOfferDetailsList();
        ProductDetails.OneTimePurchaseOfferDetails top = null;
        if (list != null) {
            for (ProductDetails.OneTimePurchaseOfferDetails o : list) {
                if (top == null || o.getPriceAmountMicros() > top.getPriceAmountMicros()) top = o;
            }
        }
        return top != null ? top : d.getOneTimePurchaseOfferDetails();
    }

    public String getPrice(String productId) {
        ProductDetails d = details.get(productId);
        if (d == null) return "";
        ProductDetails.OneTimePurchaseOfferDetails o = cheapest(d);
        return o == null ? "" : o.getFormattedPrice();
    }

    /** "price|regular price|percent off" of the cheapest offer ("" when unknown); percent 0 = not on sale. */
    public String getOffer(String productId) {
        ProductDetails d = details.get(productId);
        if (d == null) return "";
        ProductDetails.OneTimePurchaseOfferDetails lo = cheapest(d), hi = dearest(d);
        if (lo == null) return "";
        long now = lo.getPriceAmountMicros();
        Long full = lo.getFullPriceMicros();
        long regular = full != null ? full.longValue() : (hi != null ? hi.getPriceAmountMicros() : now);
        String regularText = hi != null && hi.getPriceAmountMicros() == regular ? hi.getFormattedPrice() : "";
        int pct = regular > now && regular > 0 ? Math.round(100f * (regular - now) / regular) : 0;
        return lo.getFormattedPrice() + "|" + regularText + "|" + pct;
    }

    public String ownedProducts() {
        return owned;
    }

    /** Ask Play again for paid purchases that are not finished yet (called by the game at start and now and then). */
    public void refresh() {
        if (ready) refreshPurchases();
    }

    /** The server has credited this purchase: consume it (diamond pack) or acknowledge it (skin). */
    public void finish(final String token) {
        final Purchase p = unfinished.get(token);
        if (p == null) {
            results.add("DONE|" + token + "|OK");         // already finished earlier
            return;
        }
        final String id = p.getProducts().get(0);
        if (consumable(id)) {
            client.consumeAsync(ConsumeParams.newBuilder().setPurchaseToken(token).build(), (br, t) -> {
                boolean ok = br.getResponseCode() == BillingClient.BillingResponseCode.OK;
                if (ok) unfinished.remove(token);
                results.add("DONE|" + token + "|" + (ok ? "OK" : "FAIL"));
            });
        } else if (!p.isAcknowledged()) {
            client.acknowledgePurchase(AcknowledgePurchaseParams.newBuilder().setPurchaseToken(token).build(), br -> {
                boolean ok = br.getResponseCode() == BillingClient.BillingResponseCode.OK;
                if (ok) unfinished.remove(token);
                results.add("DONE|" + token + "|" + (ok ? "OK" : "FAIL"));
            });
        } else {
            unfinished.remove(token);
            results.add("DONE|" + token + "|OK");
        }
    }

    public String pollResult() {
        String s = results.poll();
        return s == null ? "" : s;
    }

    public void buy(final String productId) {
        buy(productId, "");
    }

    /** accountTag (from the HOLO server) is stored with the purchase so the server can refuse it for any other account. */
    public void buy(final String productId, final String accountTag) {
        final ProductDetails d = details.get(productId);
        if (d == null) {
            results.add(productId + ":FAIL");
            return;
        }
        activity.runOnUiThread(() -> {
            List<BillingFlowParams.ProductDetailsParams> p = new ArrayList<>();
            BillingFlowParams.ProductDetailsParams.Builder pb = BillingFlowParams.ProductDetailsParams.newBuilder().setProductDetails(d);
            ProductDetails.OneTimePurchaseOfferDetails offer = cheapest(d);          // a running sale is what the player sees
            if (offer != null && offer.getOfferToken() != null && !offer.getOfferToken().isEmpty()) pb.setOfferToken(offer.getOfferToken());
            p.add(pb.build());
            BillingFlowParams.Builder b = BillingFlowParams.newBuilder().setProductDetailsParamsList(p);
            if (accountTag != null && !accountTag.isEmpty()) b.setObfuscatedAccountId(accountTag);
            BillingResult r = client.launchBillingFlow(activity, b.build());
            if (r.getResponseCode() != BillingClient.BillingResponseCode.OK) results.add(productId + ":FAIL");
        });
    }

    // ---- Play callbacks ----------------------------------------------------------------------------------------
    @Override
    public void onPurchasesUpdated(BillingResult r, List<Purchase> purchases) {
        if (r.getResponseCode() == BillingClient.BillingResponseCode.OK && purchases != null) {
            for (Purchase p : purchases) handle(p);
        } else if (r.getResponseCode() != BillingClient.BillingResponseCode.ITEM_ALREADY_OWNED) {
            results.add("_:FAIL");                   // cancelled / error before a product was known
        } else {
            refreshPurchases();                      // already owned: deliver it as a restore
        }
    }

    /** Paid -> reported for server delivery (never consumed here). Pending -> reported so the game can say so. */
    private void handle(final Purchase p) {
        final String id = p.getProducts().get(0);
        if (p.getPurchaseState() == Purchase.PurchaseState.PENDING) {
            results.add("PENDING|" + id);
            return;
        }
        if (p.getPurchaseState() != Purchase.PurchaseState.PURCHASED) return;
        if (!consumable(id) && p.isAcknowledged()) return;     // an old skin purchase: already delivered (ownedProducts)
        final String token = p.getPurchaseToken();
        unfinished.put(token, p);
        String order = p.getOrderId();
        results.add("BUY|" + id + "|" + token + "|" + (order == null ? "" : order));
    }
}
