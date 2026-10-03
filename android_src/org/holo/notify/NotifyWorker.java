package org.holo.notify;

import android.app.Activity;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;

import androidx.annotation.NonNull;
import androidx.work.Data;
import androidx.work.ExistingWorkPolicy;
import androidx.work.OneTimeWorkRequest;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import java.util.concurrent.TimeUnit;

/**
 * Local reminders (1.0.6): "your daily reward is ready" and a gentle come-back note. No server, no push service:
 * Python (notify.py) schedules one WorkManager job per tag through schedule(); a newer call with the same tag
 * replaces the old one, so every start of the game simply re-plans both reminders. The text arrives already
 * translated. On Android 13+ nothing shows until the player allowed notifications (askPermission()).
 */
public class NotifyWorker extends Worker {
    private static final String CHANNEL = "holo_reminders";

    public NotifyWorker(@NonNull Context context, @NonNull WorkerParameters params) {
        super(context, params);
    }

    @NonNull
    @Override
    public Result doWork() {
        Context ctx = getApplicationContext();
        String title = getInputData().getString("title");
        String text = getInputData().getString("text");
        int id = getInputData().getInt("id", 1);
        if (title == null || text == null) return Result.success();
        if (Build.VERSION.SDK_INT >= 33
                && ctx.checkSelfPermission("android.permission.POST_NOTIFICATIONS") != PackageManager.PERMISSION_GRANTED) {
            return Result.success();
        }
        NotificationManager nm = (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) return Result.success();
        if (Build.VERSION.SDK_INT >= 26) {
            nm.createNotificationChannel(new NotificationChannel(CHANNEL, "HOLO", NotificationManager.IMPORTANCE_DEFAULT));
        }
        Intent open = ctx.getPackageManager().getLaunchIntentForPackage(ctx.getPackageName());
        PendingIntent pi = open == null ? null : PendingIntent.getActivity(ctx, id, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        android.app.Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new android.app.Notification.Builder(ctx, CHANNEL)
                : new android.app.Notification.Builder(ctx);
        b.setSmallIcon(android.R.drawable.star_on)
                .setContentTitle(title)
                .setContentText(text)
                .setAutoCancel(true);
        if (pi != null) b.setContentIntent(pi);
        try {
            nm.notify(id, b.build());
        } catch (SecurityException e) {
            // permission withdrawn meanwhile
        }
        return Result.success();
    }

    /** Plans (or re-plans) the reminder `tag` to show after `delaySeconds`. */
    public static void schedule(Context ctx, String tag, long delaySeconds, String title, String text, int id) {
        Data data = new Data.Builder().putString("title", title).putString("text", text).putInt("id", id).build();
        OneTimeWorkRequest req = new OneTimeWorkRequest.Builder(NotifyWorker.class)
                .setInitialDelay(Math.max(1, delaySeconds), TimeUnit.SECONDS)
                .setInputData(data)
                .build();
        WorkManager.getInstance(ctx).enqueueUniqueWork("holo_" + tag, ExistingWorkPolicy.REPLACE, req);
    }

    public static void cancel(Context ctx, String tag) {
        WorkManager.getInstance(ctx).cancelUniqueWork("holo_" + tag);
    }

    /** Android 13+: asks once for the notification permission (the system remembers a "no"). */
    public static void askPermission(final Activity activity) {
        if (Build.VERSION.SDK_INT >= 33
                && activity.checkSelfPermission("android.permission.POST_NOTIFICATIONS") != PackageManager.PERMISSION_GRANTED) {
            activity.runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    activity.requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"}, 4711);
                }
            });
        }
    }
}
