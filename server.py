import importlib.util, json, os, time, requests, urllib3
from flask import Flask, request, jsonify
from flask_cors import CORS

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("rixor_gen", os.path.join(HERE, "rixor_gen.py"))
rixor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rixor)

GarenaAPI = rixor.GarenaAPI
Config = rixor.Config
ProtoBuilder = rixor.ProtoBuilder
SecurityEngine = rixor.SecurityEngine

app = Flask(__name__)
CORS(app)

_cache = {"jwt": None, "time": 0}

CLIENT_HOST = "clientbp.ppmainecoonghj.com"
ENDPOINT = "/GetPlayerPersonalShow"


def load_account():
    with open(os.path.join(HERE, "rixor.json")) as f:
        return json.load(f)[0]


def get_jwt():
    if _cache["jwt"] and time.time() - _cache["time"] < 1800:
        return _cache["jwt"]
    acc = load_account()
    tok_payload = json.dumps({
        "client_id": 100067, "client_secret": Config.API_HEX_KEY,
        "client_type": 2, "device_id": "02-344afb0e-593c-40b7-92f2-171972f74807",
        "password": acc['password'], "response_type": "token", "uid": acc['uid'],
    }, separators=(',', ':'))
    h = {
        "User-Agent": "GarenaMSDK/4.0.44(25028RN03A ;Android 15;ar;EG;app 1.132.1 2019121229;)",
        "Content-Type": "application/json; charset=utf-8",
        "Host": "100067.connect.garena.com",
    }
    r = requests.post("https://100067.connect.garena.com/api/v2/oauth/guest/token:grant",
                      headers=h, data=tok_payload, timeout=15, verify=False)
    d = r.json()
    if d.get("code") != 0:
        raise Exception(f"token grant failed: {d}")
    at, oid = d['data']['access_token'], d['data']['open_id']
    api = GarenaAPI()
    lang = Config.REGION_LANG.get(acc['region'], 'en')
    result = api.perform_major_login(at, oid, lang)
    if not result:
        raise Exception("major login failed")
    _cache["jwt"] = result['jwt_token']
    _cache["time"] = time.time()
    return result['jwt_token']


def decode_varint(data, pos):
    result = 0; shift = 0
    while pos < len(data):
        b = data[pos]; pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80): break
        shift += 7
    return result, pos


def is_str(b):
    try:
        s = b.decode('utf-8')
        if all(ord(c) >= 32 or c in '\t\n\r' for c in s):
            return s
    except Exception:
        pass
    return None


def parse_pb(data, depth=0):
    if depth > 4: return None
    fields = {}; pos = 0
    while pos < len(data):
        try:
            tag, pos = decode_varint(data, pos)
            fnum, wtype = tag >> 3, tag & 0x07
            if wtype == 0:
                val, pos = decode_varint(data, pos)
            elif wtype == 2:
                ln, pos = decode_varint(data, pos)
                chunk = data[pos:pos+ln]; pos += ln
                s = is_str(chunk)
                if s: val = s
                else: val = parse_pb(chunk, depth+1) or chunk.hex()
            elif wtype == 5:
                val = int.from_bytes(data[pos:pos+4], 'little'); pos += 4
            elif wtype == 1:
                val = int.from_bytes(data[pos:pos+8], 'little'); pos += 8
            else: break
            if fnum in fields:
                if not isinstance(fields[fnum], list): fields[fnum] = [fields[fnum]]
                fields[fnum].append(val)
            else: fields[fnum] = val
        except Exception: break
    return fields if fields else None


def fetch_player(uid):
    jwt = get_jwt()
    proto = ProtoBuilder.build({1: int(uid)})
    enc = bytes.fromhex(SecurityEngine.encrypt_api_payload(proto.hex()))
    h = {
        "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "Authorization": f"Bearer {jwt}",
        "X-GA": "v1 1", "ReleaseVersion": "OB55",
        "Content-Type": "application/x-www-form-urlencoded",
        "Host": CLIENT_HOST,
    }
    r = requests.post(f"https://{CLIENT_HOST}{ENDPOINT}", headers=h, data=enc, timeout=15, verify=False)
    if r.status_code != 200:
        return None
    parsed = parse_pb(r.content)
    if not parsed or not isinstance(parsed.get(1), dict):
        return None
    top = parsed[1]
    return {
        "nickname": top.get(3, "Unknown"),
        "region": top.get(5, "ME"),
        "level": top.get(6, 0),
    }


@app.route('/')
def idx():
    return jsonify({"status": "ok"})


@app.route('/validate')
def validate():
    uid = request.args.get('uid', '').strip()
    if not uid.isdigit() or not (8 <= len(uid) <= 12):
        return jsonify({"valid": False, "error": "invalid uid"}), 400
    try:
        p = fetch_player(uid)
        if not p:
            return jsonify({"valid": False, "error": "player not found"}), 404
        return jsonify({"valid": True, "uid": uid, **p})
    except Exception as e:
        return jsonify({"valid": False, "error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 4000)))
