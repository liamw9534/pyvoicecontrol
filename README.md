# pyvoicecontrol

WARNING: This README is a work in progress.

`pyvoicecontrol` is a python framework for developing voice commanded applications.
The initial focus for the development is to provide a robust audio processing pipeline
that can locally detect a spoken hotword (e.g., "alexa") using a hotword detector and
then record subsequent speech for the purpose of determining a user intent via a speech-to-text
cloud service.

The use of a local hotword detector has many benefits to any voice commanded application:

* Does not require continuous streaming of audio over the internet
* Does not require lots of CPU processing or speech recognition models that take forever to
  train to get even a mediocre level accuracy
* Can be used to alert the end user (e.g., via an audible beep) that they are entering
  into a command dialog and helps to avoid unintentional usage

The package also provides some examples of additional services that can be integrated with the
hotword detector, such as a multi-room media player using spotify, by using wit.ai as a
speech-to-text backend service.

## Dependencies

This project uses `snowboy` for hotword detection.  See https://github.com/seasalt-ai/snowboy for
more information about what `snowboy` is.

The audio processing pipeline is implemented using `gstreamer-1.14`.  There are also two
bespoke `gstreamer` plugins that have been developed for this project that must be compiled for your
system to use this application.  These are:

* `gst-snowboy` - available at https://github.com/liamw9534/snowboy/tree/gst-plugin.
* `gst-removesilence` - available at https://github.com/liamw9534/gst-removesilence; this is a slightly
  customised derivative of the excellent `removesilence` gst plugin that is shipped as standard with 1.19
  version of `gstreamer` to make the VAD a bit easier to manage.

Both these plugins must be compiled for your target machine architecture and added to your
`GST_PLUGIN_PATH` for `pyvoicecontrol` to run correctly.  Refer to their respective README documents
for information on how to do this.  Thse plugins should compile for `armhf` and `x86_64` platforms
without too much trouble.

A reference implementation of a speech-to-text backend client uses Wit.AI for decoding speech intents.
More information on this can be found later on.  Also refer to http://wit.ai to learn about Wit.AI.

## Installing & Launching

Run the command `python setup.py install` to install the application and its dependencies.  Then
launch the application with:

	pyvoicecontrol --config <yourconfigfile>

## Configuration file

A configuration file is required to configure the numerous modules that are included with `pyvoicecontrol`.
Which modules you enable depends on your needs.

### Example configuration file

Below is an example configuration file.

```
[logging]
enable = true
level = info

[snowboy]
enable = true
vad_max_silence_period_sec=5.0
vad_min_silence_period_sec=1.0

[wit_speech]
enable = true
token = <your wit ai model token>   # Refer to http://wit.ai docs
tail_discard_samples = 8000

[audio_alerts]
enable = true
volume = 0.1
triggers =
  /speech/detector:state:DETECT_START:dong.wav,
  /speech/detector:state:DETECT_STOP:ding.wav,
  /speech/detector:state:DETECT_ABORT:dong.wav

[spotify]
client_id = <your client id>           # Refer to https://developer.spotify.com/dashboard
client_secret = <your client secret>   # Refer to https://developer.spotify.com/dashboard
redirect_uri = <your redirect url>     # Refer to https://developer.spotify.com/dashboard
limit = 50                             # Max number of search result retrieved
device = Snapcast    # This is your spotify connect device name

[snapcast]
enable = true
server = 192.168.68.115
own_location = office
volume_step_size = 10
local_volume_control = yes
volume_ducking = yes

[bluetooth]
enable = true
devices =
	3B:82:04:35:EC:08,
	DC:2C:26:D1:19:25
disconnect_on_exit = false

[input]
enable = true
devices = Satechi Media Button Consumer Control
action_map =
	KEY_PLAYPAUSE:playpause,
	KEY_NEXTSONG:skip_track,
	KEY_PREVIOUSSONG:previous_track,
	KEY_VOLUMEUP:volume_louder,
	KEY_VOLUMEDOWN:volume_quieter

[pulse]
enable = true
own_location = office
echo_cancel = yes
src_vol = 100
local_volume_control = no
volume_ducking = no
```

## Modules

Below is a list of built-in modules:

* `spotify` - uses the spotify web api to allow voice control of music play back using spotify connect.
* `snapcast` - uses the snapcast json/rpc api to control to manage the volume of snapcast clients on your network
* `snowboy` - implements an audio processing pipeline to perform hotword detection and speech capture.
* `bluetooth` - implements basic bluetooth management automation for pairing and connecting to bluetooth devices e.g., speakers.
* `witservice` - implements a http client that sends captured audio waveforms to wit.ai and disseminates the returned speech to text intents.
* `input` - implements detection of input device key presses and event dissemination.
* `audio_alerts` - implements event-based audio alerts to notify the user when certain actions have arisen e.g., hotword detected.
* `pulse` - implements PulseAudio source and sink detection with optional echo cancellation and volume control

A more detailed description of these services is provided below.

## Service Architecture

All the modules in `pyvoicecontrol` are implemented against a base service class.  Each service has a unique path name and a set of resources
that is managed by the service that is abstracted as a python `dict` object.  A service can accept requests to `get` the state of its
internal resources, to modify the state of its resources via a `set` command.  A service may also notify other services when a resource state
has changed.

To this end services are loosely coupled in that a service defines an _interface_ but the implementation of that _interface_ could
be accomplished in numerous different ways.  For example, the service `/speech/intent` implements a speech-to-text service using wit.ai.  But this
service could quite easily be implemented using google speech to text instead.

# Service interface definitions

## Speech detector (`/speech/detector`)

The `/speech/detector` service should implement audio processing and hotword detection for the platform and 
encapsulates a simple state machine.

### Properties

```
{
  "state": "LISTENING | DETECT_START | DETECT_ABORT | DETECT_DONE"
}
```

The `state` property may be one of:

* `LISTENING` - the speech detector is listening to detect a hotword.
* `DETECT_START` - the speech detector has detected a hotword and is now actively.
* `DETECT_ABORT` - the speech detector VAD did not register any input after the hotword and aborted.  See `vad_max_silence_period_sec`.
* `DETECT_DONE` - the speech detector VAD detected silence after your spoken command and deems the session to be done.  See `vad_min_silence_period_sec`.

When in the `DETECT_START` state audio samples are outputs on localhost to UDP port `port` as specified in the configuration.

A separate service at should read and buffer the audio samples on the UDP port and then send them for speech-to-text processing
to determine the user intent.  This means that the `/speech/intent` should subscribe for state changes to know when a complete
section of audio has been received before sending the audio samples off for processing.

### Configuration options

These configuration options are implemented under the `[snowboy]` configuration section by the module `snowboy.py`
which provides a default implementation of the service.

* `enable` - enable/disable loading this service.
* `resource` - snowboy detector resource file.  Should not be changed.
* `model` - snowboy detector model file.  You can train and create your own hotword model.  Refer to https://github.com/seasalt-ai/snowboy.
  The default is based on the bundled "Alexa" model provided under snowboy.
* `vad_hysteresis` - the number of audio samples used as the basis for the VAD detector, bigger number implies more latency but better VAD accuracy.
* `vad_max_silence_period_sec` - the maximum silence period after `DETECT_START` state before aborting recording.  Transitions to `DETECT_ABORT` if
                                 this time period elapses without the VAD triggering.
* `vad_min_silence_period_sec` - the minimum silence period permitted after speech has been detected in the `DETECT_START` state.
* `vad_threshold_db` - sets the VAD detection threshold in dB when in `DETECT_START` state.
* `sensitivity` - set the sensitivity of the hotword detector between 0 and 1 when in `LISTENING` state.
* `port` - defines the UDP port number on which to output audio samples during `DETECT_START`.

## Snapcast (`/snapcast`)

Snapcast is a multi-room client/server based audio media distribution system.  See https://github.com/badaix/snapcast
for more information.

The `/snapcast` service implements client controls that allows the volume and mute status of any client to be controlled
through voice commands.

The implementation requires that each `snapclient` is launched with its `--hostID` set to the location of the client.  For example, if you have three
snapcast clients in the lounge, bedroom and office then they should be launched as follows:

```
snapclient --player pulse --hostID office
snapclient --player pulse --hostID lounge
snapclient --player pulse --hostID bedroom
```

Note that the location names should match those supported by entity `room:room` in your speech intent model for the intent `volume`.  Refer
to the `/speech/intent` description below for more information.

The `snapserver` can run anywhere on your network but presently the client python library implementation requires a fixed IP address
of where the server is run, as it does not support `zeroconf` based discovery.

The `/snapcast` service subscribes to `/speech/intent` for state changes and handles any `INTENT` state transitions that carries the following
intents:

* `volume`
* `volume_louder`
* `volume_quieter`
* `mute`
* `unmute`

Additionally, the `/snapcast` services subscribes to `/speech/detector` for state `DETECT_START`, `DETECT_ABORT` and `DETECT_DONE` in order to
control audio mute at the client determined by `own_location` property.  This is done to reduce the amount of background noise when
recording the microphone input _after_ the hotword has been detected.

Note that audio will continue to play and other locations are not muted.

### Configuration options

These configuration options are implemented under the `[snapcast]` configuration section by the module `snapcast.py`
which provides a default implementation of the service.

* `enable` - enable/disable loading this service.
* `volume_step_size` e.g., 10 - for speech intents `volume_louder` and `volume_quieter` determines the volume step size used.
* `own_location` e.g., "office" - the `hostID` of the `snapclient` running in the associated location.
* `server` - the hostname or IP address of where the `snapserver` is running.
* `local_volume_control` - enable/disable local volume control from this service.
* `volume_ducking` - enable/disable volume ducking after hotword detection from this service.

## Speech intent (`/speech/intent`)

The speech intent service implements a speech-to-text translation of speech recorded during a `DETECT_START` / `DETECT_DONE`
period.  The audio is delivered from `/speech/detector` via UDP and can subsequently be offloaded to a speech-to-text cloud
service.

### Properties

```
{
  "state": "IDLE | POSTING | INTENT"
  "intent": {
    "text": "play album rush of blood to the head by coldplay",
    "intents": [
      {
        "name": "play_music",
        "confidence": 0.8849
      }
    ],
    "entities": {
      "playable_item:playable_item": [
        {
          "value": "album rush of blood to the head",
          "confidence": 0.9231,
        }
      ],
      "playable_author:playable_author": [
        {
          "value": "coldplay",
          "confidence": 0.9231,
        }
      ]
    }
  }
}
```

The `state` property may be one of:

* `IDLE` - not connected to any backend service, buffering any received audio samples over UDP in memory.
* `POSTING` - connecting or connected to a backend speech-to-text service and posting buffered audio.
* `INTENT` - finished posting to the backend speech-to-text service and disseminating the decoded intent for other services to use.

The `intent` property is a wrapped response from the speech-to-text service e.g., wit.ai.

### Configuration options

These configuration options are implemented under the `[wit_speech]` configuration section by the module `wit_service.py`
which provides a default implementation of the service.

* `enable` - enable/disable loading this service.
* `token` - the token for wit.ai authentication.  Refer to https://wit.ai/docs/http/20200513/#authentication_link.
* `content` e.g., `audio/raw` - content type field in HTTP header.
* `encoding` e.g., `signed-integer` - encoding field in HTTP header.
* `bits` e.g., `16` - bits field in HTTP header.
* `endian` e.g., `little` - endian field in HTTP header.
* `rate` e.g., `16000` - rate field in HTTP header.
* `tail_discard_samples` - number of samples to throw away at the end of the audio stream i.e., to trim out VAD silence period at end.


### Wit.AI Model

The sample implementation of this service in the file `wit_service.py` uses wit.ai.  The wit.ai model can be found at
https://wit.ai/apps/279613343751439 and is public and free to use.  Note that to use wit.ai you must have your own wit.ai (facebook) account
and generate your own access token to use the model.

#### Sound volume intents

* `volume` <level> [intent: `volume`, entities: `level:wit/number`] e.g., "volume 25" - sets the volume to 25 at the current location.
* `volume` <level> <room> [intent: `volume`, entities: `level:wit/number`, `room:room`] e.g., "volume 25 bedroom" - sets the volume to 25 in the bedroom.
* `volume` <level> in <room> [intent: `volume`, entities: `level:wit/number`, `room:room`] e.g., "volume 25 in office" - sets the volume to 25 in the office.
* `volume louder` [intent: `volume_louder` - increase volume level in present location.
* `volume quieter` [intent: `volume_quieter`] - decrease volume level in present location.
* `mute` [intent: `mute_music`] - mutes the sound in the present location
* `unmute` [intent: `unmute_music`] - unmutes the sound in the present location

Currently no entities are supported.

#### Playback control intents

* `pause music` [intent: `wit/pause_music`] - music is paused at all locations
* `resume music` [intent: `wit/resume_music`] - music is resumed at all locations
* `stop music` [intent: `wit/stop_music`] - music is stopped at all locations i.e., queued tracks are cleared.
* `play <track|album|artist>` [intent: `play_music`, entities: `playable_item`] -
   play music at all locations with `playable_item` entity set to `<track|album|artist>`.
* `play <track|album> by <artist>` [intent: `play_music`, entities: `playable_item`, `playable_author`] -
   play music at all locations with `playable_item` entity set to `<track|album>` and `playable_author` set to <artist>.
* `play artist <artist>` [intent: `play_music`, entities: `playable_item`] - 
   play music at all locations with `playable_item` entity set to `artist <artist>`.
* `play track <track>` [intent: `play_music`, entities: `playable_item`] - 
   play music at all locations with `playable_item` entity set to `track <track>`.
* `play album <album>` [intent: `play_music`, entities: `playable_item`] - 
   play music at all locations with `playable_item` entity set to `album <album>`.
* `skip track` [intent: `wit/skip_track`] - skips to the next track in the queue at all locations.
* `next track` [intent: `wit/skip_track`] - skips to the next track in the queue at all locations.
* `previous track` [intent: `wit/previous_track`] - goes to the previous track in the queue at all locations.
* `shuffle` [intent: `wit/shuffle`] - turn shuffle on for the current queued tracks
* `shuffle off` or `unshuffle` [intent: `wit/unshuffle`] - turn shuffle off
* `loop` [intent: `wit/loop`] - turn loop on for queued tracks
* `loop off` or `unloop` [intent: `wit/unloop`] - turn loop off for queued tracks

Note that when `playable_item` is prefixed with either "track", "album" or "artist" then these can be treated as a _keyword_ that
can be extracted and used as the basis for backend music service searching.  By way of an example:

	"play album rush of bloody to the head"

The entity `playable_item` will be set to "album rush of bloody to the head".  The first word "album" can be used as a _keyword_
and extracted to yield the search term "album: rush of bloody to the head".

## Spotify connect (`/spotify`)

The `/spotify` service implements a spotify connect client controller using the spotify web api.  It can be used to initiate or modify
a spotify connect session on your local network.  It can be used in combination with `librespot` or any commercial product that
uses spotify connect e.g., smart speaker, smart TV, mobile phone, computer, etc.

The implementation subscribes to the `/speech/intent` service for `INTENT` state updates.  It handles the following intents:

* `play_music` - is used to intiate a search to the spotify server and modify the current playback queue.
* `stop_music` - stop playing and clear the playback queue.
* `skip_track` - skips the currently playing track.
* `previous_track` - skips back to the previous playing track.
* `pause_music` - pause current track playback.
* `resume_music` - resume current track playback.
* `shuffle` - turn shuffle on for the current queued tracks
* `shuffle off` or `unshuffle` - turn shuffle off
* `loop` - turn loop on for queued tracks
* `loop off` or `unloop` - turn loop off for queued tracks

### Properties

NOTE: This might be extended in future to include information about the current playing track.

```
{
  "state": "READY"
}
```

The `state` property may be one of:

* `READY` - the service is ready to accept speech intents.

### Configuration options

These configuration options are implemented under the `[spotify]` configuration section by the module `spotify.py`
which provides a default implementation of the service.

To use the `spotify` module you must have a premium spotify account and you must also register an application at
https://developer.spotify.com/dashboard/applications and populate the `[spotify]` configuration seciton with your
client ID, client secret and redirect URI.  This implementation uses `pyspotify`.

* `enable` - enable/disable loading this service.
* `client_id` - client ID for your spotify application created in the developer dashboard.
* `client_secret` - client secret for your spotify application created in the developer dashboard.
* `redirect_uri` - redirect uri setup for your spotify application created in the developer dashboard.
* `device` - the spotify connect device name on your network that shall be used for sessions.
* `limit` - maximum number of search results returned by the server when performing searches.

## Input device service (`/input`)

The `/input` service allows keyboards, USB or bluetooth devices to control services.  This is done
by defining an _action map_ that maps key event codes to desired outcomes.  An example of an _action map_ is below:

```
	KEY_PLAYPAUSE:playpause,
	KEY_NEXTSONG:skip_track,
	KEY_PREVIOUSSONG:previous_track,
	KEY_VOLUMEUP:volume_louder,
	KEY_VOLUMEDOWN:volume_quieter
```

This service will emit state updates on any key event code listed in the _action map_, which subscribers may listen
to in order to carry out the desired actions.

NOTE: The default implementation at `input.py` uses the `evdev` python package.


### Properties

```
{
  "state": "IDLE | ACTION",
  "action": "playpause | skip_track | previous_track | volume_louder | volume_quieter | ..."
}
```

When `state` is set to `ACTION` then the `action` property will contain the value of the associated action.
The `state` will toggle back to `IDLE` after an `ACTION` has fired.

### Configuration options

These configuration options are implemented under the `[input]` configuration section by the module `input.py`
which provides a default implementation of the service.

* `enable` - enable/disable loading this service.
* `devices` - a comma-separated list of input devices specified by either the device name, device physical address or device path.
* `action_map` - a comma-separated list of `keycode:action` pairs

## Bluetooth service (`/bluetooth`)

The `/bluetooth` service allows the process of bluetooth device discovery, pairing and connection establishment to be automated.
This is generally only targeted towards devices that can be paired without a pin code e.g., speaker, remote media control.

### Properties

```
{
  "state": "READY",
  "devices": { "xx:xx:xx:xx:xx:xx": { "state": "SCANNING | PAIRING | CONNECTING | CONNECTED" },
               ...
             }
}
```

Any devices required to be connected should be listed under `devices` in the configuration section by their bluetooth address
`xx:xx:xx:xx:xx:xx`.  If a device has not been previously paired it will first go into `SCANNING` state and then `PAIRING` once
that device is discovered.  This may require that your device is first put into pairing mode.  After successful pairing the
device `state` will transition to `CONNECTING` and then `CONNECTED` on success.

### Configuration options

These configuration options are implemented under the `[bluetooth]` configuration section by the module `bluetooth.py`
which provides a default implementation of the service.

* `enable` - enable/disable loading this service.
* `devices` - a comma-separated list of device addresses of the form `xx:xx:xx:xx:xx:xx`.
* `disconnect_on_exit` - a boolean to denote if any connected devices should be disconnected when the application exits.

## PulseAudio cliemt service (`/audio/pulse`)

PulseAudio is a network-capable sound server program distributed via the freedesktop.org project. See
https://www.freedesktop.org/wiki/Software/PulseAudio/ for more information.

The `/audio/pulse` service implements client controls that allows the volume and mute status of the local device to be controlled
through voice commands.  The service also optionally allows _echo cancellation_ to be performed between the microphone and speaker.

The implementation requires a pulseaudio server to be running on the local device.

The `/audio/pulse` service subscribes to `/speech/intent` for state changes and handles any `INTENT` state transitions that carries the following
intents:

* `volume`
* `volume_louder`
* `volume_quieter`
* `mute`
* `unmute`

Note that these are only processed where the `room:room` entity is the same as `own_location`.

Additionally, the `/audio/pulse` services subscribes to `/speech/detector` for state `DETECT_START`, `DETECT_ABORT` and `DETECT_DONE` in order to
control audio mute on the local device.  This is done to reduce the amount of background noise when recording the microphone input _after_ the
hotword has been detected.

Note that audio will continue to play and other locations are not muted.

### Configuration options

These configuration options are implemented under the `[pulse]` configuration section by the module `pulse.py`
which provides a default implementation of the service.

* `enable` - enable/disable loading this service.
* `echo_cancel` - enable/disable loading of the `module-echo-cancel` module.
* `volume_step_size` e.g., 10 - for speech intents `volume_louder` and `volume_quieter` determines the volume step size used.
* `own_location` e.g., "office" - the `hostID` of the `snapclient` running in the associated location.
* `local_volume_control` - enable/disable local volume control from this service.
* `volume_ducking` - enable/disable volume ducking after hotword detection from this service.

# Future work

* JSON API for controlling resources over a websocket
* Javascript library implementation for websocket usage
* A simple HTTP front end
