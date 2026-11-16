"""One local IDS lifetime per ECU generation. No keys travel through the pipe."""
import json
import fcntl
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import time
import uuid


def private_directory(path):
    info=path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:
        raise ValueError('IDS directory must be private and owned')


def load_settings(path):
    data=json.loads(Path(path).read_text())
    required={'python','repository','log_directory','mode','frame_budget','expiry_ms'}
    training={'train_normal','normal_manifest','calibrate_normal','calibration_manifest'}
    optional={'measure_resources'}
    if not isinstance(data,dict) or not required<=data.keys() or data.keys()-required-training-optional:
        raise ValueError('IDS settings fields rejected')
    if 'measure_resources' in data and type(data['measure_resources']) is not bool:
        raise ValueError('IDS measure_resources must be boolean')
    if data['mode'] not in ('rules-only','rules+if'):raise ValueError('explicit IDS mode required')
    if (data['mode']=='rules+if' and not training<=data.keys()) or (data['mode']=='rules-only' and training&data.keys()):
        raise ValueError('IF requires independent training/calibration manifests; no rule fallback')
    for name in ('frame_budget','expiry_ms'):
        if type(data[name]) is not int or not 1<=data[name]<2**31:raise ValueError('invalid IDS numeric limit')
    if data['frame_budget']>36:raise ValueError('IDS frame budget exceeds packet bound')
    for name in {'python','repository','log_directory'}|training&data.keys():
        if not isinstance(data[name],str) or not Path(data[name]).is_absolute():raise ValueError('absolute IDS paths required')
    if not Path(data['python']).is_file() or not (Path(data['repository'])/'security/ids/runtime.py').is_file():
        raise ValueError('IDS interpreter/repository unavailable')
    private_directory(Path(data['log_directory']))
    return data


class OwnedIds:
    def __init__(self,settings,parent,interface,key):
        self.settings=settings;self.interface=interface;self.key=key
        self.runtime=tempfile.TemporaryDirectory(prefix='ids-',dir=parent)
        self.path=Path(self.runtime.name)
        self.socket_path=self.path/'events.sock'
        if len(os.fsencode(self.socket_path))>=108:
            self.runtime.cleanup();raise ValueError('IDS runtime socket path too long')
        self.generation=uuid.uuid4().hex
        self.logs=Path(settings['log_directory'])/('ids-'+self.generation)
        self.logs.mkdir(mode=0o700)
        self.reader=self.writer=self.peer_reader=self.peer_writer=-1
        self.log_lock=-1
        try:
            self.reader,self.writer=os.pipe2(os.O_NONBLOCK|os.O_CLOEXEC)
            self.peer_reader,self.peer_writer=os.pipe2(os.O_NONBLOCK|os.O_CLOEXEC)
            self.log_lock=os.open(self.logs/'owner.lock',os.O_CREAT|os.O_EXCL|os.O_RDWR|os.O_CLOEXEC,0o600)
            fcntl.flock(self.log_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BaseException:
            for fd in (self.reader,self.writer,self.peer_reader,self.peer_writer,self.log_lock):
                if fd>=0:os.close(fd)
            self.runtime.cleanup();raise
        self.child=None;self.stream=None;self.reported=False

    def start(self,timeout,stopping):
        ready=self.path/'ready.json'
        config=self.settings
        command=[config['python'],'-m','security.ids.runtime','--interface',self.interface,
            '--run-id','owned-ids-'+self.generation,
            '--protocol','session-v2','--session-context-fd',str(self.reader),'--secoc-key',self.key,
            '--peer-rejection-fd',str(self.peer_reader),
            '--diagnostic-socket',str(self.socket_path),'--log',str(self.logs/'events.jsonl'),
            '--ready-file',str(ready),'--parent-pid',str(os.getpid()),'--duration','1']
        if config['mode']=='rules-only':command+=['--rules-only']
        else:
            for key,flag in [('train_normal','--train-normal'),('normal_manifest','--normal-manifest'),
                ('calibrate_normal','--calibrate-normal'),('calibration_manifest','--calibration-manifest')]:
                command += [flag,config[key]]
        if config.get('measure_resources',False):command+=['--measure-resources']
        self.stream=os.fdopen(os.open(self.logs/'process.log',os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_CLOEXEC,0o600),'w')
        # The log lock remains held even if the manager dies before its child.
        self.child=subprocess.Popen(command,cwd=config['repository'],pass_fds=(self.reader,self.peer_reader,self.log_lock),
                                    stdout=self.stream,stderr=subprocess.STDOUT,umask=0o077)
        os.close(self.reader);self.reader=-1
        os.close(self.peer_reader);self.peer_reader=-1
        deadline=time.monotonic()+timeout
        while True:
            if stopping() or self.child.poll() is not None or time.monotonic()>=deadline:
                raise RuntimeError('IDS startup unavailable; battery process will run without observation')
            if ready.exists():
                try:
                    record=json.loads(ready.read_text())
                    break
                except json.JSONDecodeError:
                    pass # producer may still be completing its new readiness file
            time.sleep(.02)
        if (record.get('result')!='READY' or record.get('classification_version')!='session-observation-v1'
            or record.get('mode')!=config['mode'] or record.get('run_id')!='owned-ids-'+self.generation):
            raise RuntimeError('IDS readiness rejected')
        identity=record.get('startup_identity')
        if (not isinstance(identity,dict) or identity.get('schema')!='ids-startup-v1'
            or identity.get('mode')!=config['mode']):
            raise RuntimeError('IDS startup identity unavailable')
        if (record.get('resource_measurement',False)!=config.get('measure_resources',False)
            or identity.get('resource_measurement',False)!=config.get('measure_resources',False)):
            raise RuntimeError('IDS measurement readiness mismatch')
        print('ECU_SUPERVISOR: IDS started pid='+str(self.child.pid),flush=True)
        print(json.dumps({'result':'OWNED_IDS_READY','generation':self.generation,
            'ids_pid':self.child.pid,'mode':config['mode'],'protocol':'session-v2',
            'resource_measurement':config.get('measure_resources',False),
            'classification_version':record['classification_version'],'startup_identity':identity}),flush=True)

    def ecu_args(self):
        return ['--ids-context-fd',str(self.writer),'--ids-peer-fd',str(self.peer_writer),'--ids-socket',str(self.socket_path),
                '--ids-pid',str(self.child.pid),'--ids-frame-budget',str(self.settings['frame_budget']),
                '--ids-expiry-ms',str(self.settings['expiry_ms'])]

    def handed_off(self):
        if self.writer>=0:os.close(self.writer);self.writer=-1
        if self.peer_writer>=0:os.close(self.peer_writer);self.peer_writer=-1

    def check(self):
        if not self.reported and self.child.poll() is not None:
            self.child.wait();self.reported=True
            print('ECU_SUPERVISOR: IDS stopped; observation unavailable; ECU continues',flush=True)

    def close(self,timeout):
        for name in ('reader','writer','peer_reader','peer_writer'):
            fd=getattr(self,name)
            if fd>=0:os.close(fd);setattr(self,name,-1)
        if self.child is not None:
            if self.child.poll() is None:self.child.terminate()
            try:self.child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:self.child.kill();self.child.wait()
        if self.stream:self.stream.close()
        if self.log_lock>=0:os.close(self.log_lock);self.log_lock=-1
        self.runtime.cleanup() # unique owned directory, after ECU/IDS are reaped
