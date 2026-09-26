import os
import socket
import tempfile
import pytest
from fastapi.testclient import TestClient

os.environ['BHARATSHIELD_DATA_DIR']=tempfile.mkdtemp(prefix='bharatshield-test-')
from app import main,local_security,local_registry

@pytest.fixture(autouse=True)
def deny_outbound(monkeypatch):
    def blocked(*args,**kwargs): raise AssertionError('Outbound socket attempted')
    monkeypatch.setattr(socket.socket,'connect',blocked)

@pytest.fixture(scope='session')
def client():
    local_security.create_user('tester','Test Officer','test-password-12345','officer')
    local_security.create_user('supervisor','Test Supervisor','test-password-12345','supervisor')
    with local_registry.connection() as db:
        local_registry.create_in_transaction(db,local_registry.RegistryRecordInput(document_type='PAN Card',document_number='ABCDE1234F',name='SAMPLE PERSON',dob='1990-01-01',nationality='IND',issuer_country='IND'),'supervisor','Regression test reference record.')
    with TestClient(main.app) as c:
        assert c.post('/api/auth/login',headers={'X-Local-Request':'1'},json={'username':'tester','password':'test-password-12345'}).status_code==200
        yield c
