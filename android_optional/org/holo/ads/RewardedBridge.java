package org.holo.ads;

import android.app.Activity;

import androidx.annotation.NonNull;

import com.google.android.gms.ads.AdError;
import com.google.android.gms.ads.AdRequest;
import com.google.android.gms.ads.FullScreenContentCallback;
import com.google.android.gms.ads.LoadAdError;
import com.google.android.gms.ads.MobileAds;
import com.google.android.gms.ads.OnUserEarnedRewardListener;
import com.google.android.gms.ads.rewarded.RewardItem;
import com.google.android.gms.ads.rewarded.RewardedAd;
import com.google.android.gms.ads.rewarded.RewardedAdLoadCallback;

import java.util.concurrent.ConcurrentLinkedQueue;

/**
 * Rewarded video ads (Google Mobile Ads SDK 24.x) for ads.py - NOT built yet: it lives in android_optional/ until the
 * AdMob account exists. Switching it on is described in docs/ADS.md (move this file to android_src/, add the SDK to
 * android.gradle_dependencies and the AdMob *app* id as manifest meta-data - without that meta-data the SDK crashes
 * the app at start, which is why none of this ships before the ids are known).
 *
 * Python polls pollResult(): "REWARD" (the player watched to the end - pay now), "CLOSED", "FAIL|<code>".
 */
public class RewardedBridge {
    private final Activity activity;
    private final String unitId;
    private volatile RewardedAd ad;
    private volatile boolean loading;
    private final ConcurrentLinkedQueue<String> results = new ConcurrentLinkedQueue<>();

    public RewardedBridge(Activity activity, String unitId) {
        this.activity = activity;
        this.unitId = unitId;
        activity.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                MobileAds.initialize(RewardedBridge.this.activity);
                load();
            }
        });
    }

    private void load() {
        if (loading || ad != null) return;
        loading = true;
        RewardedAd.load(activity, unitId, new AdRequest.Builder().build(), new RewardedAdLoadCallback() {
            @Override
            public void onAdLoaded(@NonNull RewardedAd r) {
                ad = r;
                loading = false;
            }

            @Override
            public void onAdFailedToLoad(@NonNull LoadAdError e) {
                ad = null;
                loading = false;
            }
        });
    }

    public boolean ready() {
        return ad != null;
    }

    public void show() {
        activity.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                final RewardedAd r = ad;
                if (r == null) {
                    results.add("FAIL|notready");
                    load();
                    return;
                }
                ad = null;
                r.setFullScreenContentCallback(new FullScreenContentCallback() {
                    @Override
                    public void onAdDismissedFullScreenContent() {
                        results.add("CLOSED");
                        load();
                    }

                    @Override
                    public void onAdFailedToShowFullScreenContent(@NonNull AdError e) {
                        results.add("FAIL|" + e.getCode());
                        load();
                    }
                });
                r.show(activity, new OnUserEarnedRewardListener() {
                    @Override
                    public void onUserEarnedReward(@NonNull RewardItem item) {
                        results.add("REWARD");
                    }
                });
            }
        });
    }

    public String pollResult() {
        String s = results.poll();
        return s == null ? "" : s;
    }
}
