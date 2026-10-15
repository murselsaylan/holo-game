package org.holo.review;

import android.app.Activity;

import com.google.android.play.core.review.ReviewInfo;
import com.google.android.play.core.review.ReviewManager;
import com.google.android.play.core.review.ReviewManagerFactory;

/**
 * Google Play's in-app review sheet ("Rate HOLO"), used from Python through pyjnius (review.py).
 * Play decides by itself whether the sheet really appears (it has a quota per user), and never tells whether the player
 * rated - the game only asks at good moments and moves on.
 *
 * state(): "" before ask(), "ASKING" while Play prepares / shows the sheet, then "DONE" or "FAIL|reason".
 * Needs (buildozer.spec): com.google.android.play:review.
 */
public class ReviewBridge {
    private final Activity activity;
    private final ReviewManager manager;
    private volatile String state = "";

    public ReviewBridge(Activity activity) {
        this.activity = activity;
        this.manager = ReviewManagerFactory.create(activity);
    }

    public void ask() {
        state = "ASKING";
        activity.runOnUiThread(() -> manager.requestReviewFlow().addOnCompleteListener(request -> {
            if (!request.isSuccessful()) {
                Exception e = request.getException();
                state = "FAIL|" + (e != null ? e.getClass().getSimpleName() : "request");
                return;
            }
            ReviewInfo info = request.getResult();
            manager.launchReviewFlow(activity, info).addOnCompleteListener(flow -> state = "DONE");
        }));
    }

    public String state() {
        return state;
    }
}
