import json
import argparse
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--check', action='store_true', help='Fail if checked-in contracts have drifted')
args = parser.parse_args()
root=Path(__file__).resolve().parent.parent
string={'type':'string'}
move={'type':'object','additionalProperties':False,'required':['asset_id','rack_id','u','face','expected_revision','authority_epoch','site','idempotency_key'],'properties':{'asset_id':string,'rack_id':string,'u':{'type':'integer','minimum':1},'face':{'enum':['front','rear']},'expected_revision':{'type':'integer','minimum':1},'authority_epoch':{'type':'integer','minimum':1},'site':string,'idempotency_key':{'type':'string','minLength':1,'maxLength':100}}}
contracts={
'inventory':{'/assets':['get'],'/assets/{asset_id}':['get','patch']},
'placement':{'/scene':['get'],'/preview':['post'],'/reservations':['post'],'/reservations/{request_id}/commit':['post']},
'workflow':{'/changes':['get','post'],'/changes/{change_id}/approve':['post'],'/changes/{change_id}/execute':['post']},
'synchronization':{'/status':['get'],'/rehearsal':['post'],'/conflicts/{conflict_id}/resolve':['post']},
'registry':{'/modules':['get'],'/preflight':['post']}}
for service,paths in contracts.items():
    doc={'openapi':'3.1.0','info':{'title':'UnumDCIM '+service,'version':'0.1.0','description':'Foundation API. Production human access requires signed OIDC access tokens with MFA; synthetic static identities are demo-only.'},'servers':[{'url':'/api/v1'}],'security':[{'bearer':[]}],'paths':{},'components':{'securitySchemes':{'bearer':{'type':'http','scheme':'bearer'}},'schemas':{'MoveProposal':move}}}
    for path,methods in paths.items():
        ops={}
        for method in methods:
            operation={'operationId':service+'_'+method+'_'+path.replace('/','_').replace('{','').replace('}',''), 'responses':{'200':{'description':'Successful result'},'400':{'description':'Invalid input'},'401':{'description':'Authentication required'},'403':{'description':'Scope or role denied'},'409':{'description':'Revision, ownership, occupancy or workflow conflict'},'503':{'description':'Dependency temporarily unavailable'}}}
            if method=='post':operation['responses']['201']={'description':'Created when applicable'}
            names=[x[1:-1] for x in path.split('/') if x.startswith('{')]
            if names:operation['parameters']=[{'name':n,'in':'path','required':True,'schema':string} for n in names]
            schema=None
            if service=='workflow' and path=='/changes' and method=='post':schema={'$ref':'#/components/schemas/MoveProposal'}
            elif path.endswith('/approve'):schema={'type':'object','required':['expected_revision'],'properties':{'expected_revision':{'type':'integer'}}}
            elif path.endswith('/resolve'):schema={'type':'object','required':['expected_revision','candidate'],'properties':{'expected_revision':{'type':'integer'},'candidate':string}}
            elif method=='patch':schema={'type':'object','additionalProperties':False,'required':['name','expected_revision'],'properties':{'name':{'type':'string','minLength':1,'maxLength':160},'expected_revision':{'type':'integer'}}}
            elif method=='post':schema={'type':'object','description':'See service contract and synthetic rehearsal examples; reserved foundation operation.'}
            if schema:operation['requestBody']={'required':True,'content':{'application/json':{'schema':schema}}}
            ops[method]=operation
        doc['paths'][path]=ops
    if service == 'placement':
        doc['paths']['/reservations']['post']['description'] = 'Creates a reservation under the authenticated tenant/site scope or returns an existing reservation for the same request ID and command. The service credential and delegated caller credential are both verified; effective scope is their intersection. A definitive validation rejection has code plan_invalid.'
        operation = doc['paths']['/reservations/{request_id}/commit']['post']
        operation['description'] = 'Atomically confirms placement and records the committed revision. Repeating a committed request returns that revision without moving again, even after the original expiry time. Expired or invalid held reservations become terminal and release their hold.'
        operation['responses']['409']['description'] = 'Terminal rejection with code reservation_expired or reservation_invalid; create a newly approved plan with a new request ID.'
    if service == 'workflow':
        doc['components']['schemas']['ChangeState'] = {'type': 'string', 'enum': ['awaiting_approval', 'awaiting_nlyte', 'approved', 'executing', 'replan_required', 'completed']}
        operation = doc['paths']['/changes/{change_id}/execute']['post']
        operation['description'] = 'Executes or resumes one approved move with a stable reservation ID. Transient dependency failures retain executing; retry the same change ID. Definitive reservation expiry or plan rejection transitions to terminal replan_required. Refresh placement, submit a new proposal with a new idempotency key and obtain a separate approval. Completed retries return the recorded result without moving twice.'
        operation['responses']['409']['description'] = 'Definitive plan rejection may return the change in replan_required. Repeated execution of that terminal change returns code replan_required.'
        operation['responses']['503']['description'] = 'Outcome may be ambiguous; the change stays executing and must be retried using the same change ID.'
    destination = root/'contracts/openapi'/f'{service}.json'
    content = json.dumps(doc,indent=2)+'\n'
    if args.check:
        if not destination.exists() or json.loads(destination.read_text()) != doc:
            raise SystemExit(f'OpenAPI drift: {destination.relative_to(root)}; run scripts/write_openapi.py')
    else:
        destination.write_text(content)
