"""Generate the checked-in foundation manifests; no production support claims."""
import json
from pathlib import Path
root = Path(__file__).resolve().parent.parent
contracts = {'inventory':'unum.inventory/1','placement':'unum.scene/1','workflow':'unum.changes/1','synchronization':'unum.sync-status/1','registry':'unum.modules/1','twin':'unum.twin/1'}
modules = ['access','inventory','placement','power','cooling','cabling','capacity','workflow','library','synchronization','telemetry','reporting','twin','registry']
for name in modules:
    dependencies = {'workflow':{'inventory':'unum.inventory/1','placement':'unum.scene/1'}, 'twin':{'inventory':'unum.inventory/1','placement':'unum.scene/1'}}.get(name,{})
    data = {'manifest_version':1,'id':name,'version':'0.1.0','status':'implemented' if name in contracts else 'planned',
            'maturity':'foundation' if name in contracts else 'design','release_channel':'development','supported_until':'2026-12-31',
            'provides':[contracts[name]] if name in contracts else [],'requires':dependencies,
            'tested_with':{d:['0.1.0'] for d in dependencies},'permissions':[],
            'artifact':None,'migration':{'phase':'expand','compatible_application_versions':['0.1.0']},
            'notes':'Local foundation only. No LTS or HA qualification. Published artifacts are not available.'}
    (root/'contracts/modules'/f'{name}.json').write_text(json.dumps(data,indent=2)+'\n')
