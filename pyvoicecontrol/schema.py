
enable_schema = {'type': bool, 'default': True }
enable_schema_false = {'type': bool, 'default': False }
debug_level_schema = {'type': str, 'allowed_values': ['error', 'warn', 'info', 'debug'], 'default': 'info' }

schema = {
    'logging': {
        'enable': enable_schema,
        'level': debug_level_schema,
        'path': {'type': str, 'default':'/logging' },
        'port': {'type': int, 'default': 51010 },
    },
    'snowboy': {
        'enable': enable_schema,
        'path': {'type': str, 'default': '/speech/detector' },
        'resource': {'type': str, 'default': 'common.res' },
        'model': {'type': str, 'default': 'alexa_02092017.umdl' },
        'port': {'type': int, 'default': 5050 },
        'vad_hysteresis': {'type': int, 'default': 480 },
        'vad_threshold_db': {'type': int, 'default': -40 },
        'vad_min_silence_period_sec': {'type': float, 'default': 1.25 },
        'vad_max_silence_period_sec': {'type': float, 'default': 5 },
        'sensitivity': {'type': str, 'default': '0.5' },
        'pipeline': {'type': str,
                     'default': 'pulsesrc ! snowboy name=sb resource={} models={} sensitivity={} ! removesilence name=rm hysteresis={} remove=0 threshold={} minimum-silence-time={} silent=1 gate=1 ! udpsink host=127.0.0.1 port={} sync=false' },
    },
    'wit_speech': {
        'enable': enable_schema,
        'path': {'type': str, 'default':'/speech/intent' },
        'port': {'type': int, 'default': 5050 },
        'token': {'type': str },
        'output_file': {'type': str, 'default': '' },
        'content': {'type': str, 'default': 'audio/raw' },
        'encoding': {'type': str, 'default': 'signed-integer' },
        'bits': {'type': int, 'default': 16 },
        'rate': {'type': int, 'default': 16000 },
        'endian': {'type': str, 'default': 'little' },
        'url': {'type': str, 'default': 'https://api.wit.ai/speech'},
        'tail_discard_samples': {'type': int, 'default': 0 }
    },
    'audio_alerts': {
        'enable': enable_schema,
        'path': {'type': str, 'default':'/audio/alerts' },
        'triggers': {'type': list, 'subtype': str },
        'volume': {'type': float, 'default': 1 },
        'pipeline': {'type': str, 'default':'playbin uri=file://{} volume={}' },
    },
    'spotify': {
        'enable': enable_schema,
        'path': {'type': str, 'default':'/spotify' },
        'client_id': {'type': str },
        'client_secret': {'type': str },
        'redirect_uri': {'type': str },
        'device': {'type': str },
        'limit': {'type': int, 'default': 10 },
        'scan_period': {'type': float, 'default': 60 },
    },
    'snapcast': {
        'enable': enable_schema,
        'path': {'type': str, 'default':'/snapcast' },
        'own_location': {'type': str },
        'volume_step_size': {'type': int, 'default': 10 },
        'local_volume_control': {'type': bool, 'default': False },
        'volume_ducking': {'type': bool, 'default': False },
        'server': {'type': str },
    },
    'bluetooth': {
        'enable': enable_schema,
        'path': {'type': str, 'default':'/bluetooth' },
        'devices': {'type': list, 'subtype': str },
        'disconnect_on_exit': enable_schema_false
    },
    'input': {
        'enable': enable_schema,
        'path': {'type': str, 'default':'/input' },
        'devices': {'type': list, 'subtype': str, 'default': [] },
        'action_map': {'type': list, 'subtype': str, 'default': [] },
    },
    'pulse': {
        'enable': enable_schema,
        'path': {'type': str, 'default':'/audio/pulse' },
        'src_vol': {'type': int, 'default': None },
        'sink_vol': {'type': int, 'default': None },
        'echo_cancel': {'type': bool, 'default': False },
        'local_volume_control': {'type': bool, 'default': False },
        'volume_step_size': {'type': int, 'default': 10 },
        'volume_ducking': {'type': bool, 'default': False },
        'own_location': {'type': str },
    },
}
