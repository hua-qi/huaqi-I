import os

replacements = [
    ('huaqi_src.layers.data.events.models',              'huaqi_src.layers.data.events.models'),
    ('huaqi_src.layers.data.events.store',         'huaqi_src.layers.data.events.store'),
    ('huaqi_src.layers.capabilities.llm.manager',                'huaqi_src.layers.capabilities.llm.manager'),
    ('huaqi_src.layers.data.profile.models',     'huaqi_src.layers.data.profile.models'),
    ('huaqi_src.layers.data.profile.manager',    'huaqi_src.layers.data.profile.manager'),
    ('huaqi_src.layers.data.profile.narrative',  'huaqi_src.layers.data.profile.narrative'),
    ('huaqi_src.layers.capabilities.pattern.engine',   'huaqi_src.layers.capabilities.pattern.engine'),
    ('huaqi_src.layers.capabilities.care.engine',     'huaqi_src.layers.capabilities.care.engine'),
    ('huaqi_src.layers.data.flexible.store',     'huaqi_src.layers.data.flexible.store'),
    ('huaqi_src.cli.ui_utils',           'huaqi_src.cli.ui_utils'),
    ('huaqi_src.layers.data.git.auto_commit',    'huaqi_src.layers.data.git.auto_commit'),
]

changed = []
for dirp, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d != '__pycache__' and not d.startswith('.')]
    for fname in files:
        if not fname.endswith('.py'):
            continue
        fpath = os.path.join(dirp, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        new = content
        for old, new_val in replacements:
            new = new.replace(old, new_val)
        if new != content:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(new)
            changed.append(fpath)

print(f'Updated {len(changed)} files')
for fp in sorted(changed):
    print(f'  {fp}')
