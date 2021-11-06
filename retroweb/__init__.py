import signal

from pyramid.config import Configurator

from retroweb.stream import DEFAULT_STREAM_DESTINATION
from retroweb.stream import RetroArchController


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    rac = RetroArchController(DEFAULT_STREAM_DESTINATION)
    rac.start('/usr/bin/retroarch')
    signal.signal(signal.SIGINT, rac.stop)

    config = Configurator(settings=settings)
    config.include('pyramid_jinja2')
    config.include('.models')
    config.include('.routes')
    config.scan()
    config.registry["display"] = rac.display

    print("DISPLAY", rac.display)

    return config.make_wsgi_app()
