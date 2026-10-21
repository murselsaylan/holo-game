package org.holo.share;

import android.app.Activity;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.provider.MediaStore;

import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.OutputStream;

/**
 * Share sheet for the share card (share.py): the png is added to the gallery (MediaStore, Pictures/HOLO - no storage
 * permission and no FileProvider needed on Android 10+) and handed to ACTION_SEND together with the text. Before Android
 * 10 the picture cannot be added without a storage permission, so only the text is shared there.
 */
public class ShareBridge {
    private final Activity activity;

    public ShareBridge(Activity activity) {
        this.activity = activity;
    }

    public void share(final String path, final String text) {
        activity.runOnUiThread(() -> {
            try {
                Intent send = new Intent(Intent.ACTION_SEND);
                send.putExtra(Intent.EXTRA_TEXT, text);
                Uri uri = Build.VERSION.SDK_INT >= 29 ? insert(path) : null;
                if (uri != null) {
                    send.setType("image/png");
                    send.putExtra(Intent.EXTRA_STREAM, uri);
                    send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                } else {
                    send.setType("text/plain");
                }
                activity.startActivity(Intent.createChooser(send, null));
            } catch (Exception e) {
                android.util.Log.w("HOLO", "share failed", e);
            }
        });
    }

    private Uri insert(String path) {
        try {
            File f = new File(path);
            ContentResolver cr = activity.getContentResolver();
            ContentValues v = new ContentValues();
            v.put(MediaStore.Images.Media.DISPLAY_NAME, f.getName());
            v.put(MediaStore.Images.Media.MIME_TYPE, "image/png");
            v.put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/HOLO");
            Uri uri = cr.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, v);
            if (uri == null) return null;
            try (InputStream in = new FileInputStream(f); OutputStream out = cr.openOutputStream(uri)) {
                byte[] buf = new byte[16384];
                int n;
                while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
            }
            return uri;
        } catch (Exception e) {
            android.util.Log.w("HOLO", "share: could not add the picture", e);
            return null;
        }
    }
}
