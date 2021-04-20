import sys
import pykka
import argparse


from pyvoicecontrol import config, schema, logserv, snowboy, witservice, audio_alerts, spotify, snapcast, bluetooth, input, pulse

from gi.repository import Gst, GObject
from gi import require_version
require_version('Gst', '1.0')

Gst.init(None)

parser = argparse.ArgumentParser()
parser.add_argument('--config_file', type=argparse.FileType('r'), required=True)
args = parser.parse_args()
sys_cfg = config.parse_config(args.config_file, schema.schema)


def start_services(cfg):
    if cfg['snowboy']['enable']:
        snowboy.SnowboyHotwordDetector.start(cfg['snowboy'])
    if cfg['logging']['enable']:
        logserv.LogService.start(cfg['logging'])
    if cfg['wit_speech']['enable']:
        witservice.WitAISpeechService.start(cfg['wit_speech'])
    if cfg['audio_alerts']['enable']:
        audio_alerts.AudioAlerts.start(cfg['audio_alerts'])
    if cfg['spotify']['enable']:
        spotify.SpotifyService.start(cfg['spotify'])
    if cfg['snapcast']['enable']:
        snapcast.Snapcast.start(cfg['snapcast'])
    if cfg['bluetooth']['enable']:
        bluetooth.Bluetooth.start(cfg['bluetooth'])
    if cfg['input']['enable']:
        input.Input.start(cfg['input'])
    if cfg['pulse']['enable']:
        pulse.Pulse.start(cfg['pulse'])


def stop_services():
    pykka.ActorRegistry.stop_all()


def main():
    if not any(vars(args).values()):
        parser.print_help()
        sys.exit(2)

    print('Starting services...')
    start_services(sys_cfg)
    print('Done.')

    try:
        loop = GObject.MainLoop()
        loop.run()
    except KeyboardInterrupt:
        print('User abort, cleaning up...')
    finally:
        print('Stopping services...')
        stop_services()
        print('Done.')
        if loop:
            loop.quit()


if __name__ == "__main__":
    main()
