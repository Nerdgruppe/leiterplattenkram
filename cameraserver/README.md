# Camera Server


Setup:

```sh-session
[felix@xqwork cameraserver]$ python -m venv .venv
(.venv) [felix@xqwork cameraserver]$ .venv/bin/activate
(.venv) [felix@xqwork cameraserver]$ pip install -r requirements.txt
```

Drei einzelne Jobs aktuell:

```sh-session
(.venv) [felix@xqwork cameraserver]$ .venv/bin/activate
(.venv) [felix@xqwork cameraserver]$ just frontend
(.venv) [felix@xqwork cameraserver]$ just backend
(.venv) [felix@xqwork cameraserver]$ just webrtc
```
