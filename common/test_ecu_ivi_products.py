"""Actual ECU plus actual Qt IVI, public dummy key, existing virtual CAN only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import socket
import struct
import sys


def complete_observation_rows(path):
    # The live writer may be between chunks of one UTF-8 JSON line. Only a
    # newline commits a row; completed malformed rows still fail the fixture.
    data = path.read_bytes()
    committed = data[:data.rfind(b'\n')+1]
    return [json.loads(line) for line in committed.decode('utf-8').splitlines() if line.strip()]


def stop(child):
    if child is None:
        return
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=3)


def inject_virtual_attack(name,attack,one_pair=False):
    # This fixture receives/sends only on a validated existing virtual bus.
    # It receives no key, session context, MAC verifier or SSH capability.
    with socket.socket(socket.AF_CAN,socket.SOCK_RAW,socket.CAN_RAW) as bus:
        bus.bind((name,));bus.settimeout(.02)
        pair=[]
        if attack=="replay":
            until=time.monotonic()+.6;raw=None
            while time.monotonic()<until and not pair:
                try:packet=bus.recv(16)
                except socket.timeout:continue
                cid,dlc,data=struct.unpack("=IB3x8s",packet)
                if cid==0x100 and dlc==8:raw=data
                elif cid==0x102 and dlc==8 and raw is not None:pair=[(0x100,raw),(0x102,data)]
            if not pair:raise RuntimeError("no raw replay pair observed")
        if one_pair:
            time.sleep(.05)
            for cid,data in pair:bus.send(struct.pack("=IB3x8s",cid,8,data))
            return
        rate=1000 if attack=="flooding" else 100 if attack=="fuzzy" else 10
        end=time.monotonic()+.5;count=0
        while time.monotonic()<end:
            if attack=="replay":frames=pair
            elif attack=="spoofing":frames=[(0x100,bytes.fromhex("c9c80f3cffec4100"))]
            elif attack=="fuzzy":frames=[((0x050,0x060,0x070)[count%3],bytes(8))]
            else:frames=[(0x080,bytes(8))]
            for cid,data in frames:bus.send(struct.pack("=IB3x8s",cid,8,data))
            count+=1;time.sleep(1/rate)


def verify_incident_history(output, records, linked):
    """Compare persisted claims with actual authenticated/local product evidence."""
    exported=output/'event-export'
    exporter=Path(__file__).resolve().parent.parent/'ivi_platform/scripts/export_event_history.py'
    subprocess.run([sys.executable,str(exporter),'--directory',str(output/'event-store'),
                    '--out',str(exported)],check=True,capture_output=True,text=True,timeout=5)
    manifest=json.loads((exported/'manifest.json').read_text())
    data=(exported/'events.jsonl').read_bytes()
    if manifest['status']!='COMPLETE' or manifest['writer_marker_present'] or manifest['contains_gap_annotations']:
        raise RuntimeError('event journal did not close with complete committed evidence')
    if hashlib.sha256(data).hexdigest()!=manifest['sha256']:
        raise RuntimeError('export checksum mismatch')
    events=[json.loads(line)['event'] for line in data.splitlines()]
    if len(events)!=manifest['records']:
        raise RuntimeError('export record count mismatch')
    incidents={}
    types={1:'fuzzy',2:'replay',3:'spoofing',4:'flooding'}
    for row in records:
        if row.get('result')=='AUTHENTICATED_DIAGNOSTIC' and row.get('kind')==4:
            body=bytes.fromhex(row['body_hex'])
            incidents[body[16:32].hex()]=types[body[32]]
    refusals={bytes.fromhex(row['body_hex'])[16:32].hex() for row in records
              if row.get('result')=='LOCAL_REJECTION_RECORD' and bytes.fromhex(row['body_hex'])[32]==7}
    typed=[item for event in events for item in event.get('typed_incidents',[])]
    nodes={(bytes.fromhex(row['body_hex'])[:16].hex(),row['session_id'])
           for row in records if row.get('result')=='AUTHENTICATED_DIAGNOSTIC' and row.get('kind')==1}
    processes=[event['ecu_process'] for event in events if 'ecu_process' in event]
    if not processes or any((process['instance_id'],process['session_id']) not in nodes for process in processes):
        raise RuntimeError('persisted ECU process identity missing authenticated NodeStatus evidence')
    if not any(item['attack_type']=='replay' for item in typed):
        raise RuntimeError('actual Replay incident was not persisted/exported')
    for item in typed:
        if incidents.get(item['incident_id'])!=item['attack_type']:
            raise RuntimeError('stored incident/type not found in authenticated CAN evidence')
        if 'rejection_id' in item and item['rejection_id'] not in refusals:
            raise RuntimeError('stored refusal not found in actual local verifier evidence')
    linked_events=[event for event in events if event['category']=='incident-data-refusal']
    if linked:
        if not any(item['attack_type']=='replay' and item.get('rejection_id') in refusals
                   for event in linked_events for item in event.get('typed_incidents',[])):
            raise RuntimeError('confirmed actual Replay/refusal link missing from committed export')
    elif linked_events or any('rejection_id' in item for item in typed):
        raise RuntimeError('ambiguous actual candidates falsely linked in committed export')
    return {'records':len(events),'typed_entries':len(typed),'confirmed_link_expected':linked,
            'authenticated_process_records':len(processes),
            'authenticated_incident_ids':len(incidents),'local_refusal_ids':len(refusals)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ecu", required=True)
    parser.add_argument("--ivi", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--ids-check", action="store_true")
    parser.add_argument("--rejection-check", action="store_true")
    parser.add_argument("--incident-link-check", action="store_true")
    parser.add_argument("--incident-ambiguous-check", action="store_true")
    parser.add_argument("--real-ids-check", action="store_true")
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--out", type=Path, help="new result directory, no key retained")
    output.add_argument("--out-parent", type=Path, help="create a unique test result directory below this parent")
    parser.add_argument("--ids-attack",choices=("flooding","fuzzy","replay","spoofing"))
    args = parser.parse_args()
    if args.incident_ambiguous_check and (not args.rejection_check or args.incident_link_check):parser.error("ambiguous check requires repeated replay rejection test")
    if args.incident_link_check and not args.rejection_check:parser.error("incident link check requires replay rejection check")
    if args.rejection_check and (not args.real_ids_check or args.ids_attack!="replay"):parser.error("rejection check requires actual replay IDS")
    if args.ids_attack and not args.real_ids_check:parser.error("attack check requires actual IDS")
    if args.ids_check and args.real_ids_check:parser.error("fixture and actual IDS checks are separate")
    name = os.environ.get("CAPSTONE_SESSION_TEST_INTERFACE", "")
    if not name:
        print("SKIP: CAPSTONE_SESSION_TEST_INTERFACE not selected")
        return 77
    if not name.startswith("vcan") or "/" in name or not Path("/sys/devices/virtual/net", name).is_dir():
        raise ValueError("product integration requires existing virtual vcan")
    if args.out_parent:
        args.out_parent.mkdir(parents=True, exist_ok=True)
        args.out = Path(tempfile.mkdtemp(prefix="pair-", dir=args.out_parent)) / "results"
    args.out.mkdir(parents=True, exist_ok=False)
    history_args=[]
    if args.incident_link_check or args.incident_ambiguous_check:
        store=args.out/'event-store';store.mkdir(mode=0o700)
        event_policy=args.out/'event-policy.json'
        event_policy.write_text(json.dumps({'directory':str(store.resolve()),'segment_bytes':65536,
            'total_bytes':1048576,'warning_bytes':524288,'min_free_bytes':1,'queue_capacity':64}))
        history_args=['--event-policy',str(event_policy)]
    ecu = ivi = ids = None
    context_reader=context_writer=None
    peer_reader=peer_writer=None
    ids_log=None
    with tempfile.TemporaryDirectory(prefix="capstone-products-key-") as private:
        key = Path(private) / "public-dummy.bin"
        key.write_bytes(bytes(range(32)))
        key.chmod(0o600)
        runtime = Path(private) / "runtime"
        runtime.mkdir(mode=0o700)
        environment = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                           XDG_RUNTIME_DIR=str(runtime))
        ready = args.out / "ready.json"
        observations = args.out / "observations.jsonl"
        screenshot = args.out / "dashboard.png"
        with (args.out / "ecu.log").open("w") as ecu_log, (args.out / "ivi.log").open("w") as ivi_log:
            try:
                ivi = subprocess.Popen([args.ivi, "--interface", name, "--secoc-key", str(key),
                                        "--protocol", "session-v2", "--session-policy", args.policy,
                                        "--ready-file", str(ready), "--observation-jsonl", str(observations),
                                        "--run-id", "CHG029-PRODUCT-PAIR", "--windowed",
                                        "--demo-exit-ms", "6500" if args.incident_link_check or args.incident_ambiguous_check else "3500", "--screenshot", str(screenshot),
                                        "--screenshot-after-ms", "1800"] + history_args + (["--rejection-queue","4","--rejection-frame-budget","2","--rejection-expiry-ms","5000"] if args.rejection_check else []),
                                       env=environment, stdout=ivi_log, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 5
                while not ready.exists():
                    if ivi.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError("actual IVI failed READY; inspect ivi.log")
                    time.sleep(0.02)
                ids_path=str(Path(private)/"ids.sock")
                ids_args=(["--ids-socket",ids_path,"--ids-pid",str(os.getpid()),
                           "--ids-frame-budget","2","--ids-expiry-ms","1000"] if args.ids_check else [])
                if args.real_ids_check:
                    context_reader,context_writer=os.pipe2(os.O_NONBLOCK|os.O_CLOEXEC)
                    peer_reader,peer_writer=os.pipe2(os.O_NONBLOCK|os.O_CLOEXEC)
                    ids_ready=Path(private)/"ids-ready.json"
                    ids_log=(args.out/"ids-stdout.log").open("w")
                    ids=subprocess.Popen([sys.executable,"-m","security.ids.runtime","--interface",name,
                        "--rules-only","--protocol","session-v2","--session-context-fd",str(context_reader),
                        "--peer-rejection-fd",str(peer_reader),
                        "--secoc-key",str(key),"--diagnostic-socket",ids_path,
                        "--log",str(args.out/"ids.jsonl"),"--ready-file",str(ids_ready),"--duration","10"],
                        cwd=str(Path(__file__).resolve().parent.parent),stdout=ids_log,stderr=subprocess.STDOUT,
                        pass_fds=(context_reader,peer_reader))
                    os.close(context_reader);context_reader=None
                    os.close(peer_reader);peer_reader=None
                    deadline=time.monotonic()+3
                    while not ids_ready.exists():
                        if ids.poll() is not None or time.monotonic()>deadline:raise RuntimeError("actual IDS failed READY")
                        time.sleep(.01)
                    ids_args=["--ids-socket",ids_path,"--ids-pid",str(ids.pid),"--ids-frame-budget","2",
                              "--ids-expiry-ms","1000","--ids-context-fd",str(context_writer),"--ids-peer-fd",str(peer_writer)]
                ecu = subprocess.Popen([args.ecu, "--interface", name, "--sensor-mode", "constant",
                                        "--secoc", "on", "--protocol", "session-v2", "--session-policy", args.policy,
                                        "--key", str(key)]+ids_args, stdout=ecu_log, stderr=subprocess.STDOUT,
                                       pass_fds=(context_writer,peer_writer) if context_writer is not None else ())
                if context_writer is not None:os.close(context_writer);context_writer=None
                if peer_writer is not None:os.close(peer_writer);peer_writer=None
                if args.ids_check:
                    deadline=time.monotonic()+2
                    while not Path(ids_path).exists():
                        if ecu.poll() is not None or time.monotonic()>deadline:raise RuntimeError("IDS endpoint unavailable")
                        time.sleep(.01)
                    time.sleep(.5)
                    source=bytes.fromhex("00000000000040008000000000000001")
                    body=source+bytes((1,0,0,0))+struct.pack('>IQIIII',1,1000,1000,20,0,1000)+bytes((8,0,3,0))
                    with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as sender:
                        sender.sendto(b'CID2'+bytes((7,len(body)))+(time.monotonic_ns()//1_000_000).to_bytes(8,'big')+body,ids_path)
                if args.ids_attack:
                    if args.incident_link_check or args.incident_ambiguous_check:
                        deadline=time.monotonic()+4
                        while True:
                            rows=[]
                            if observations.exists():
                                rows=complete_observation_rows(observations)
                            if any(row.get('observation_ready') and row.get('condition_mask')==0 for row in rows):break
                            if time.monotonic()>deadline:raise RuntimeError("no healthy baseline for unique candidate test")
                            time.sleep(.02)
                    else:time.sleep(.4)
                    inject_virtual_attack(name,args.ids_attack,one_pair=args.incident_link_check)
                ivi_code = ivi.wait(timeout=10)
                if ids is not None and ids.poll() is not None:
                    ids_log.flush()
                    if "IDS stopped: receive clock mapping" in (args.out/"ids-stdout.log").read_text():
                        invalid={"status":"INVALID","reason":"CLOCK_MAPPING_UNAVAILABLE","scope":"virtual environment; no classification verdict"}
                        (args.out/"summary.json").write_text(json.dumps(invalid,indent=2)+"\n")
                        print("SKIP: IDS clock mapping guard rejected this observation; logs retained")
                        return 77
                if ivi_code != 0 or ecu.poll() is not None or (ids is not None and ids.poll() is not None):
                    raise RuntimeError("actual product exited with failure; inspect ECU/IVI logs")
            finally:
                stop(ids)
                if ids_log:ids_log.close()
                for descriptor in (context_reader,context_writer,peer_reader,peer_writer):
                    if descriptor is not None:os.close(descriptor)
                stop(ivi)
                stop(ecu)
    records = [json.loads(line) for line in observations.read_text().splitlines() if line.strip()]
    service = [row for row in records if row.get("result") == "SESSION_PUBLICATION"]
    model = [row for row in records if row.get("result") == "VIEW_MODEL_PUBLICATION"]
    if len(service) < 10 or len(model) < 10 or not screenshot.is_file() or screenshot.stat().st_size == 0:
        raise RuntimeError("missing actual service/ViewModel publications or screenshot")
    if any(not row["valid"] or row["stale"] or int(row["session_generation"]) != 1 or row["soh"] != 100 for row in service):
        raise RuntimeError("actual IVI service did not reflect authenticated current BMS")
    expected_name={"flooding":"Flooding","fuzzy":"Fuzzy","replay":"Replay","spoofing":"Spoofing"}.get(args.ids_attack)
    allowed_security=("보안 감시 확인 중","새 보안 알림 없음")+(expected_name,) if expected_name else (("보안 감시 확인 중","Flooding") if args.ids_check else (("보안 감시 확인 중","새 보안 알림 없음") if args.real_ids_check else ("보안 감시 확인 중",)))
    if any(row["connection"] != "현재 수신값" or row["security"] not in allowed_security or row["soh"] != 100 or
           not int(row["t1_received_ns"]) <= int(row["t2_published_ns"]) <= int(row["t3_view_model_ns"]) for row in model):
        raise RuntimeError("actual Qt ViewModel values/clock order differ")
    if args.ids_check:
        diagnostics=[row for row in records if row.get("result")=="AUTHENTICATED_DIAGNOSTIC"]
        if not any(row["kind"]==7 and row["condition_mask"]==8 and row["observation_ready"] for row in diagnostics):
            raise RuntimeError("IDS local submission did not reach authenticated IVI service")
        if not any(row["security"]=="Flooding" for row in model):
            raise RuntimeError("IDS condition did not reach actual Qt ViewModel")
    if not any(any("IVI 수신 큐 유실: 0건" in line for line in row.get("flooding_metrics", [])) for row in model):
        raise RuntimeError("actual IVI socket drop measurement did not reach ViewModel")
    if args.real_ids_check:
        ids_rows=[json.loads(line) for line in (args.out/"ids.jsonl").read_text().splitlines() if line.strip()]
        actual_types={row['attack_type'] for row in ids_rows if row.get('attack_type',0)}
        expected_types={"fuzzy":1,"replay":2,"spoofing":3,"flooding":4}
        if args.ids_attack:
            if actual_types!={expected_types[args.ids_attack]}:raise RuntimeError("actual IDS type mismatch: "+str(actual_types))
            if not any(row['security']==expected_name for row in model):raise RuntimeError("typed attack missing from actual Qt UI")
        elif actual_types:raise RuntimeError("normal product traffic raised typed IDS attack")
        diagnostics=[row for row in records if row.get("result")=="AUTHENTICATED_DIAGNOSTIC"]
        if not any(row['kind']==7 and row['observation_ready'] for row in diagnostics):
            raise RuntimeError("actual IDS never delivered healthy authenticated observation")
        if not any(row['result']=='OBSERVATION_STATUS' and bytes.fromhex(row['body_hex'])[49:51]==bytes((0,4)) for row in ids_rows):
            raise RuntimeError("session IDS revision missing")
    if args.rejection_check:
        replay_records=[bytes.fromhex(row['body_hex']) for row in records if row.get('result')=='LOCAL_REJECTION_RECORD' and bytes.fromhex(row['body_hex'])[32]==7]
        ecu_text=(args.out/"ecu.log").read_text()
        if not any('record_id='+body[16:32].hex() in ecu_text for body in replay_records):
            raise RuntimeError("ECU report UUID did not match actual IVI rejection record")
        if "IVI_REJECTION reason=7 mac_verified=1 treatment=1 reference_kind=2" not in (args.out/"ecu.log").read_text():
            raise RuntimeError("actual verifier replay report did not reach ECU over authenticated CAN")
        consumed=[row for row in ids_rows if row.get('result')=='PEER_REJECTION_CONSUMED' and row.get('reason')==7]
        matching=[row for row in consumed if any(row['body_hex']==body.hex() and row['rejection_id']==body[16:32].hex() for body in replay_records)]
        if not matching or any(not row['diagnostic_only'] or row['attack_type_inferred'] or row['if_features_changed'] for row in matching):
            raise RuntimeError('actual IVI authenticated rejection did not reach the IDS diagnostic consumer intact')
        if not any("재전송 데이터를 확인해" in row.get("rejection_summary","") for row in model):
            raise RuntimeError("actual replay refusal was not displayed by Qt")
    if args.incident_link_check:
        if not any(any("Replay · 관련 데이터의 수신 거부 확인"==text for text in row.get('incident_treatments',[])) for row in model):
            raise RuntimeError("single attested incident did not link to the actual local rejection")
    if args.incident_ambiguous_check:
        if any(any("수신 거부 확인" in text for text in row.get('incident_treatments',[])) for row in model):
            raise RuntimeError("ambiguous repeated candidates were falsely attributed")
    history_result=None
    if history_args:
        history_result=verify_incident_history(args.out,records,args.incident_link_check)
    sequences = [int(row["measurement_sequence"]) for row in service]
    if sequences != sorted(set(sequences)):
        raise RuntimeError("service published duplicate or unordered measurements")
    result = {"status": "PASS", "scope": "actual ECU main and actual Qt IVI Service/ViewModel over Linux vcan; no physical CAN",
              "service_measurements": len(service), "view_model_measurements": len(model),
              "session_generation": 1, "ambiguous_incident_left_unconfirmed":args.incident_ambiguous_check, "incident_link_verified":args.incident_link_check, "rejection_roundtrip_verified":args.rejection_check, "real_session_ids":args.real_ids_check, "ids_attack":args.ids_attack, "rendered_screenshot": "dashboard.png", "ecu_exit": ecu.returncode,
              "ivi_exit": ivi.returncode, "note": "public dummy key removed; host raw logs require review before sharing"}
    if args.rejection_check:result['ids_peer_rejection_matches']=len(matching)
    if result["ecu_exit"] != 0 or result["ivi_exit"] != 0:
        raise RuntimeError("product did not stop cleanly")
    if history_result is not None:result['verified_incident_history']=history_result
    (args.out / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
