"""Hands a picture + text to the phone's share sheet (Android ACTION_SEND via android_src/org/holo/share/ShareBridge.java,
iOS UIActivityViewController through rubicon-objc). Desktop: nothing opens - the png is already saved, the caller says
where. Returns True when a share sheet was asked for."""
import paths

_bridge = None
_tried = False


def _android():
    global _bridge, _tried
    if not _tried:
        _tried = True
        try:
            from jnius import autoclass     # python-for-android only
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            _bridge = autoclass("org.holo.share.ShareBridge")(activity)
        except Exception as e:
            print("share unavailable:", e)
            _bridge = None
    return _bridge


def _ios(path, text):
    from rubicon.objc import ObjCClass

    def p(obj, name):
        v = getattr(obj, name)
        return v() if callable(v) else v

    image = ObjCClass("UIImage").imageWithContentsOfFile_(path)
    items = ObjCClass("NSMutableArray").alloc().init()
    if image is not None:
        items.addObject_(image)
    items.addObject_(ObjCClass("NSString").stringWithString_(text))
    ctl = ObjCClass("UIActivityViewController").alloc().initWithActivityItems_applicationActivities_(items, None)
    app = p(ObjCClass("UIApplication"), "sharedApplication")
    win = p(app, "keyWindow") or p(p(app, "windows"), "firstObject")
    vc = p(win, "rootViewController")
    while p(vc, "presentedViewController") is not None:
        vc = p(vc, "presentedViewController")
    pop = p(ctl, "popoverPresentationController")       # iPad: the sheet is a popover and needs an anchor
    if pop is not None:
        pop.setSourceView_(p(vc, "view"))
        pop.setSourceRect_(p(p(vc, "view"), "bounds"))
    vc.presentViewController_animated_completion_(ctl, True, None)


def send(path, text):
    try:
        if paths.is_android():
            b = _android()
            if b is not None:
                b.share(path, text)
                return True
        elif paths.is_ios():
            _ios(path, text)
            return True
    except Exception as e:
        print("share failed:", e)
    return False
