"""Screen areas the game must not draw its controls under on phones: the camera cut-out / status bar at the top
and the gesture pill / navigation buttons at the bottom. Values are physical pixels, (top, bottom)."""
import paths


def insets_px(screen_h):
    """(top, bottom) insets in physical pixels. Desktop: (0, 0). Android: read from the window; if that fails,
    a conservative guess so the controls still stay clear of a camera hole."""
    if paths.is_ios():
        return _ios_insets(screen_h)
    if not paths.is_android():
        return 0, 0
    top = bottom = None
    try:
        from jnius import autoclass  # provided by python-for-android
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        wi = activity.getWindow().getDecorView().getRootWindowInsets()
        if wi is not None:
            top = bottom = 0
            try:                                   # Android 9+: camera cut-out
                cut = wi.getDisplayCutout()
                if cut is not None:
                    top, bottom = cut.getSafeInsetTop(), cut.getSafeInsetBottom()
            except Exception:
                pass
            try:                                   # Android 11+: status / navigation bars, even while hidden
                bars = wi.getInsetsIgnoringVisibility(autoclass("android.view.WindowInsets$Type").systemBars())
                top, bottom = max(top, bars.top), max(bottom, bars.bottom)
            except Exception:
                top = max(top, wi.getStableInsetTop())
                bottom = max(bottom, wi.getStableInsetBottom())
    except Exception as e:
        print("safe area: fallback", e)
    if top is None:
        top, bottom = int(screen_h * 0.035), int(screen_h * 0.02)
    cap = int(screen_h * 0.08)                     # never give away more than 8% at either edge
    return max(0, min(cap, int(top))), max(0, min(cap, int(bottom)))


def _ios_insets(screen_h):
    """iPhone notch / Dynamic Island and home indicator, from UIKit's safe area (points, scaled to the window)."""
    top = bottom = None
    try:
        from rubicon.objc import ObjCClass   # shipped with the pygame-ios template
        app = ObjCClass("UIApplication").sharedApplication
        win = app.keyWindow or app.windows.firstObject
        if win is not None:
            ins = win.safeAreaInsets
            h_pt = float(ObjCClass("UIScreen").mainScreen.bounds.size.height)
            k = screen_h / max(1.0, h_pt)
            top, bottom = ins.top * k, ins.bottom * k
    except Exception as e:
        print("safe area (iOS): fallback", e)
    if top is None:                              # notch phones: ~6% / 4% of the height
        top, bottom = screen_h * 0.06, screen_h * 0.04
    cap = int(screen_h * 0.08)
    return max(0, min(cap, int(top))), max(0, min(cap, int(bottom)))
