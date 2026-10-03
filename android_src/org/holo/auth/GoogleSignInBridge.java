package org.holo.auth;

import android.app.Activity;
import android.os.CancellationSignal;

import androidx.credentials.Credential;
import androidx.credentials.CredentialManager;
import androidx.credentials.CredentialManagerCallback;
import androidx.credentials.CustomCredential;
import androidx.credentials.GetCredentialRequest;
import androidx.credentials.GetCredentialResponse;
import androidx.credentials.exceptions.GetCredentialException;
import androidx.credentials.exceptions.NoCredentialException;

import com.google.android.libraries.identity.googleid.GetGoogleIdOption;
import com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption;
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential;

import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.Executors;

/**
 * "Sign in with Google" through Android's Credential Manager, used from Python through pyjnius (google_auth.py).
 * Shows Google's own account chooser; the ID token that comes back is sent to the HOLO server, which checks it with
 * Google's keys and links the pilot to that Google account (account recovery after a reinstall / on a new phone).
 *
 * Python polls pollResult(): "OK|<id token>"  or  "FAIL|<reason>"  ("" while nothing happened).
 * Needs (buildozer.spec): androidx.credentials:credentials, credentials-play-services-auth, googleid; enable_androidx.
 */
public class GoogleSignInBridge {
    private final Activity activity;
    private final CredentialManager manager;
    private final ConcurrentLinkedQueue<String> results = new ConcurrentLinkedQueue<>();

    public GoogleSignInBridge(Activity activity) {
        this.activity = activity;
        this.manager = CredentialManager.create(activity);
    }

    /** serverClientId = the OAuth "Web application" client id; onlyAuthorized = only accounts used with HOLO before.
     *  The quick account sheet first; when it finds no account to offer (NoCredentialException - it happens on some
     *  phones that do have a Google account) the full "Sign in with Google" screen is shown instead. */
    public void signIn(final String serverClientId, final boolean onlyAuthorized) {
        final GetGoogleIdOption option = new GetGoogleIdOption.Builder()
                .setFilterByAuthorizedAccounts(onlyAuthorized)
                .setServerClientId(serverClientId)
                .setAutoSelectEnabled(false)
                .build();
        request(new GetCredentialRequest.Builder().addCredentialOption(option).build(), serverClientId, true);
    }

    private void request(final GetCredentialRequest request, final String serverClientId, final boolean canFallBack) {
        activity.runOnUiThread(() -> manager.getCredentialAsync(activity, request, new CancellationSignal(),
                Executors.newSingleThreadExecutor(),
                new CredentialManagerCallback<GetCredentialResponse, GetCredentialException>() {
                    @Override
                    public void onResult(GetCredentialResponse response) {
                        Credential c = response.getCredential();
                        // the quick sheet and the full "Sign in with Google" screen answer with two type names
                        // (..._CREDENTIAL / ..._SIWG_CREDENTIAL) of the same Google ID token credential
                        if (c instanceof CustomCredential && c.getType() != null
                                && c.getType().contains("GOOGLE_ID_TOKEN")) {
                            try {
                                GoogleIdTokenCredential g = GoogleIdTokenCredential.createFrom(c.getData());
                                results.add("OK|" + g.getIdToken());
                            } catch (Exception e) {
                                results.add("FAIL|parse");
                            }
                        } else {
                            results.add("FAIL|type");
                        }
                    }

                    @Override
                    public void onError(GetCredentialException e) {
                        if (canFallBack && e instanceof NoCredentialException) {
                            GetSignInWithGoogleOption full = new GetSignInWithGoogleOption.Builder(serverClientId).build();
                            request(new GetCredentialRequest.Builder().addCredentialOption(full).build(), serverClientId, false);
                            return;
                        }
                        String kind = e.getClass().getSimpleName();         // e.g. GetCredentialCancellationException
                        results.add("FAIL|" + kind);
                    }
                }));
    }

    public String pollResult() {
        String s = results.poll();
        return s == null ? "" : s;
    }
}
