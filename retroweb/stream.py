import asyncio
import json
import logging
import os
import subprocess
import sys
import time
import uuid

from aiohttp import web
from aiortc import MediaStreamTrack
from aiortc import RTCPeerConnection
from aiortc import RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole
from aiortc.contrib.media import MediaPlayer
from aiortc.contrib.media import MediaRecorder
from aiortc.contrib.media import MediaRelay
from av import VideoFrame
import click
from xvfbwrapper import Xvfb


ROOT = os.path.dirname(__file__)

logger = logging.getLogger("peer")


class BroadcastStreams(object):

    def __init__(self):
        self._peers = {}
        self._relay = MediaRelay()

    async def offer(self, request):
        params = await request.json()
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

        peer = RTCPeerConnection()
        peer_id = "PeerConnection(%s)" % uuid.uuid4()
        self._peers[peer_id] = peer

        def log_info(msg, *args):
            logger.info(peer_id + " " + msg, *args)

            log_info("Created for %s", request.remote)

        # prepare local media
        player = MediaPlayer(os.path.join(ROOT, "demo-instruct.wav"))
        if args.record_to:
            recorder = MediaRecorder(args.record_to)
        else:
            recorder = MediaBlackhole()

        @peer.on("datachannel")
        def on_datachannel(channel):
            @channel.on("message")
            def on_message(message):
                if isinstance(message, str) and message.startswith("ping"):
                    channel.send("pong" + message[4:])

        @peer.on("connectionstatechange")
        async def on_connectionstatechange():
            log_info("Connection state is %s", peer.connectionState)
            if peer.connectionState == "failed":
                await peer.close()
                self._peers.discard(peer)

        @peer.on("track")
        def on_track(track):
            log_info("Track %s received", track.kind)

            if track.kind == "audio":
                peer.addTrack(player.audio)
                recorder.addTrack(track)
            elif track.kind == "video":
                peer.addTrack(self._relay.subscribe(track))

            @track.on("ended")
            async def on_ended():
                log_info("Track %s ended", track.kind)
                await recorder.stop()

        # handle offer
        await peer.setRemoteDescription(offer)
        await recorder.start()

        # send answer
        answer = await peer.createAnswer()
        await peer.setLocalDescription(answer)

        return web.Response(
            content_type="application/json",
            text=json.dumps(
                {
                    "sdp": peer.localDescription.sdp,
                    "type": peer.localDescription.type,
                }
            ),
        )

    async def on_shutdown(self, app):
        # close peer connections
        coros = [pc.close() for pc in self._peers]
        await asyncio.gather(*coros)
        self._peers = None


@click.command('broadcast', help="WebRTC audio / video / data-channels demo")
@click.option('-c', '--cert-file', type=click.Path())
@click.option('-k', '--key-file', type=click.Path())
@click.option('-h', '--host', type=str, default='0.0.0.0')
@click.option('-p', '--port', type=str, default=8080)
@click.option('-v', '--verbose', type=int, count=True)
def _broadcast():
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="WebRTC audio / video / data-channels demo"
    )

    if args.cert_file:
        ssl_context = ssl.SSLContext()
        ssl_context.load_cert_chain(args.cert_file, args.key_file)
    else:
        ssl_context = None

    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    app.router.add_get("/client.js", javascript)
    app.router.add_post("/offer", offer)
    web.run_app(
        app, access_log=None, host=args.host, port=args.port, ssl_context=ssl_context
    )
DEFAULT_STREAM_DESTINATION = "/usr/local/nginx/html/streams/retroarch.m3u8"


class RetroArchController(object):

    def __init__(self, destination):
        self._destination = destination
        self._xvfb = None
        self._retroarch = None
        self._streamer = None

    @property
    def display(self):
        return self._xvfb and self._xvfb.new_display

    def start(self, application_command):
        self.run(application_command)
        self.stream(self.display)

    def run(self, application_command):
        self._xvfb = Xvfb(
            width=1280,
            height=720,
            colordepth=24,
        )
        self._xvfb.start()
        self._retroarch = self._run_app(
            application_command,
            self._xvfb.new_display,
        )
        return self._xvfb.new_display

    def stop(self):
        if self._streamer is not None:
            self._streamer.kill()
            self._streamer.wait()
            print(self._streamer)
        if self._retroarch is not None:
            self._retroarch.kill()
            self._retroarch.wait()
        if self._xvfb is not None:
            self._xvfb.stop()

    def hls(self, display):
        pass

    def stream(self, display):
        stream_args = [
            '/usr/bin/ffmpeg',
            '-f', 'x11grab', '-s', '1280x720', '-r', '24',
            '-i', ":{}".format(display),
            '-c:v', 'h264', '-preset', 'superfast',
            '-flags', '+cgop', '-g', '30',
            self._destination,
        ]
        print(stream_args)
        self._streamer = subprocess.Popen(stream_args)

    def _run_app(self, application_args, display):
        retroarch_env = {
            "DISPLAY": ":{}".format(display),
            "XDG_RUNTIME_DIR": os.environ['XDG_RUNTIME_DIR'],
        }
        retroarch = subprocess.Popen(
            application_args,
            env=retroarch_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        return retroarch


@click.group()
def main():
    pass


@main.command('stream-app')
@click.argument("app-command", type=str, nargs=-1)
@click.option("--destination", type=str, default=DEFAULT_STREAM_DESTINATION)
def _stream_app(app_command, destination):
    retrostream = RetroArchController(destination)
    try:
        app_display = retrostream.run(app_command)
        print(app_display, file=sys.stderr, flush=True)
        retrostream.stream(app_display)
        while time.sleep(16):
            pass
    finally:
        print("STOPPING")
        retrostream.stop()
        sys.exit()


@main.command('launch-app')
@click.argument("app-command", type=str, nargs=-1)
@click.option("--destination", type=str, default=DEFAULT_STREAM_DESTINATION)
def _launch_app(app_command, destination):
    retrostream = RetroArchController(destination)
    retrostream.run(app_command)


@main.command('stream-display')
@click.argument("display", type=int)
@click.option("--destination", type=str, default=DEFAULT_STREAM_DESTINATION)
def _stream_display(display, destination):
    retrostream = RetroArchController(destination)
    retrostream.stream(display)

