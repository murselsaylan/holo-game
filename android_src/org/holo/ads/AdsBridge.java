package org.holo.ads;

import android.app.Activity;

import androidx.annotation.NonNull;

import com.google.android.gms.ads.AdError;
import com.google.android.gms.ads.AdRequest;
import com.google.android.gms.ads.FullScreenContentCallback;
import com.google.android.gms.ads.LoadAdError;
import com.google.android.gms.ads.MobileAds;
import com.google.android.gms.ads.interstitial.InterstitialAd;
import com.google.android.gms.ads.interstitial.InterstitialAdLoadCallback;
import com.google.android.gms.ads.rewarded.RewardedAd;
import com.google.android.gms.ads.rewarded.RewardedAdLoadCallback;
import com.google.android.gms.ads.rewardedinterstitial.RewardedInterstitialAd;
import com.google.android.gms.ads.rewardedinterstitial.RewardedInterstitialAdLoadCallback;
import com.google.android.ump.ConsentInformation;
import com.google.android.ump.ConsentRequestParameters;
import com.google.android.ump.UserMessagingPlatform;

import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Google Mobile Ads for ads.py: three slots, each keeps one ad loaded.
 *   "diamonds"  rewarded ad              (the player chooses to watch -> diamonds)
 *   "continue"  rewarded interstitial    (keep playing after a crash)
 *   "levels"    interstitial             (every few levels; removed by the "remove_ads" purchase)
 * Before any ad request the UMP consent message is shown where the law asks for it (EEA / UK) - only then is the
 * SDK started. Python polls pollResult(): "slot|REWARD", "slot|CLOSED" or "slot|FAIL|reason".
 */
public class AdsBridge {
    private final Activity activity;
    private final String[] ids = new String[3];          // diamonds, continue, levels
    private final Object[] ads = new Object[3];
    private final boolean[] loading = new boolean[3];
    private final ConcurrentLinkedQueue<String> results = new ConcurrentLinkedQueue<>();
    private final AtomicBoolean started = new AtomicBoolean(false);
    private ConsentInformation consent;

    public AdsBridge(Activity activity, String diamondsId, String continueId, String levelsId) {
        this.activity = activity;
        ids[0] = diamondsId;
        ids[1] = continueId;
        ids[2] = levelsId;
        activity.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                askConsent();
            }
        });
    }

    private static int slot(String name) {
        if ("diamonds".equals(name)) return 0;
        if ("continue".equals(name)) return 1;
        return 2;
    }

    private static String name(int i) {
        return i == 0 ? "diamonds" : (i == 1 ? "continue" : "levels");
    }

    // ---------------------------------------------------------------- consent, then the SDK
    private void askConsent() {
        try {
            consent = UserMessagingPlatform.getConsentInformation(activity);
            ConsentRequestParameters params = new ConsentRequestParameters.Builder().build();
            consent.requestConsentInfoUpdate(activity, params,
                    new ConsentInformation.OnConsentInfoUpdateSuccessListener() {
                        @Override
                        public void onConsentInfoUpdateSuccess() {
                            UserMessagingPlatform.loadAndShowConsentFormIfRequired(activity,
                                    new com.google.android.ump.ConsentForm.OnConsentFormDismissedListener() {
                                        @Override
                                        public void onConsentFormDismissed(com.google.android.ump.FormError e) {
                                            startIfAllowed();
                                        }
                                    });
                        }
                    },
                    new ConsentInformation.OnConsentInfoUpdateFailureListener() {
                        @Override
                        public void onConsentInfoUpdateFailure(@NonNull com.google.android.ump.FormError e) {
                            startIfAllowed();
                        }
                    });
            startIfAllowed();                           // consent from an earlier start: no need to wait
        } catch (Throwable t) {
            startIfAllowed();
        }
    }

    private void startIfAllowed() {
        if (consent != null && !consent.canRequestAds()) return;
        if (!started.compareAndSet(false, true)) return;
        MobileAds.initialize(activity, status -> {
            for (int i = 0; i < 3; i++) load(i);
        });
    }

    /** True when the game should offer "privacy options" (only in regions that need a consent form). */
    public boolean privacyOptionsRequired() {
        return consent != null && consent.getPrivacyOptionsRequirementStatus()
                == ConsentInformation.PrivacyOptionsRequirementStatus.REQUIRED;
    }

    public void showPrivacyOptions() {
        activity.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                UserMessagingPlatform.showPrivacyOptionsForm(activity, e -> startIfAllowed());
            }
        });
    }

    // ---------------------------------------------------------------- loading
    private void load(final int i) {
        if (ids[i] == null || ids[i].isEmpty() || loading[i] || ads[i] != null) return;
        loading[i] = true;
        AdRequest req = new AdRequest.Builder().build();
        if (i == 0) {
            RewardedAd.load(activity, ids[i], req, new RewardedAdLoadCallback() {
                @Override
                public void onAdLoaded(@NonNull RewardedAd ad) { ads[0] = ad; loading[0] = false; }
                @Override
                public void onAdFailedToLoad(@NonNull LoadAdError e) { loading[0] = false; }
            });
        } else if (i == 1) {
            RewardedInterstitialAd.load(activity, ids[i], req, new RewardedInterstitialAdLoadCallback() {
                @Override
                public void onAdLoaded(@NonNull RewardedInterstitialAd ad) { ads[1] = ad; loading[1] = false; }
                @Override
                public void onAdFailedToLoad(@NonNull LoadAdError e) { loading[1] = false; }
            });
        } else {
            InterstitialAd.load(activity, ids[i], req, new InterstitialAdLoadCallback() {
                @Override
                public void onAdLoaded(@NonNull InterstitialAd ad) { ads[2] = ad; loading[2] = false; }
                @Override
                public void onAdFailedToLoad(@NonNull LoadAdError e) { loading[2] = false; }
            });
        }
    }

    public boolean ready(String slotName) {
        int i = slot(slotName);
        if (ads[i] == null && started.get()) {
            activity.runOnUiThread(() -> load(i));      // e.g. the first load failed while offline: try again
        }
        return ads[i] != null;
    }

    // ---------------------------------------------------------------- showing
    public void show(String slotName) {
        final int i = slot(slotName);
        activity.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                final Object ad = ads[i];
                if (ad == null) {
                    results.add(name(i) + "|FAIL|notready");
                    load(i);
                    return;
                }
                ads[i] = null;
                final boolean[] rewarded = {false};
                FullScreenContentCallback cb = new FullScreenContentCallback() {
                    @Override
                    public void onAdDismissedFullScreenContent() {
                        if (rewarded[0]) results.add(name(i) + "|REWARD");
                        results.add(name(i) + "|CLOSED");
                        load(i);
                    }

                    @Override
                    public void onAdFailedToShowFullScreenContent(@NonNull AdError e) {
                        results.add(name(i) + "|FAIL|" + e.getCode());
                        load(i);
                    }
                };
                if (ad instanceof RewardedAd) {
                    ((RewardedAd) ad).setFullScreenContentCallback(cb);
                    ((RewardedAd) ad).show(activity, item -> rewarded[0] = true);
                } else if (ad instanceof RewardedInterstitialAd) {
                    ((RewardedInterstitialAd) ad).setFullScreenContentCallback(cb);
                    ((RewardedInterstitialAd) ad).show(activity, item -> rewarded[0] = true);
                } else {
                    ((InterstitialAd) ad).setFullScreenContentCallback(cb);
                    ((InterstitialAd) ad).show(activity);
                }
            }
        });
    }

    /** Next event for Python, or "" when nothing happened. */
    public String pollResult() {
        String r = results.poll();
        return r == null ? "" : r;
    }
}
