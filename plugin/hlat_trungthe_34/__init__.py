def classFactory(iface):
    from .plugin import HlatPlugin
    return HlatPlugin(iface)
