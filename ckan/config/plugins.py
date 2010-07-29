import pkg_resources

def plugin_loader(loader, global_config, main='main', plugins=''):
    for plugin in plugins.split():
        app = loader.get_app(plugin)
        print app.__class__
        print dir(app)
        #entry_point = pkg_resources.EntryPoint.parse("plugin = " + plugin)
        #plugin_module = __import__(entry_point.module_name)
        #print plugin_module
        #plugin_app = loader.get_app(plugin)
    app = loader.get_app(main)
    #for plugin in plugins.split():
    #    filter = loader.get_filter(plugin)
    #    app = filter(app)
    return app