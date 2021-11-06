def includeme(config):
    config.add_static_view('static', 'static', cache_max_age=3600)
    config.add_route('home', '/')
    config.add_route('stream', '/stream')
    config.add_route("console_controls", "/console/controls")
    config.add_route("console_display", "/console/display")
