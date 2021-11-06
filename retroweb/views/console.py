from pyramid.view import view_config


@view_config(
    route_name="stream",
    renderer="retroweb:templates/stream.jinja2",
)
def stream_endpoint(request):
    return {"display": request.registry["display"]}


@view_config(route_name="console_controls")
def console_controls(request):
    pass


@view_config(route_name="console_display")
def console_display(request):
    pass
