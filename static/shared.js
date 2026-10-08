const I = {
  users: [], epics: [], statuses: [], sprints: [], scope: 'unscheduled',
  el(tag, text, cls) {
    const e = document.createElement(tag);
    if (text != null) e.textContent = text;
    if (cls) e.className = cls;
    return e;
  },
  async api(path, method = 'GET', body) {
    const r = await fetch(path, {method, headers: body === undefined ? {} : {'Content-Type':'application/json'}, body: body === undefined ? undefined : JSON.stringify(body)});
    const data = await r.json();
    if (!r.ok) {
      const detail = data.detail;
      throw new Error(Array.isArray(detail) ? detail.map(d => `${d.loc.at(-1)}: ${d.msg}`).join('; ') : detail || `Request failed (${r.status})`);
    }
    return data;
  },
  message(text, error = false) {
    const e = document.getElementById('notice');
    e.textContent = text; e.hidden = !text; e.className = `notice${error ? ' error' : ''}`;
    e.setAttribute('role', error ? 'alert' : 'status');
  },
  async run(action) {
    try { await action(); } catch(e) { this.message(e.message || 'Unable to connect. Please retry.', true); }
  },
  async refs() {
    [this.users, this.epics, this.statuses, this.sprints] = await Promise.all(['users','epics','statuses','sprints'].map(n => this.api(`/api/${n}/`)));
  },
  month(month) {
    const [y,m] = month.split('-').map(Number);
    const d = new Date(2000, m - 1, 1); d.setFullYear(y);
    return d.toLocaleDateString(undefined, {month:'long',year:'numeric'});
  },
  sprintName(id) { const s = this.sprints.find(s => s.id === id); return s ? this.month(s.month) : 'Unscheduled'; },
  options(select, items, value) {
    select.replaceChildren(...items.map(([v,t]) => new Option(t,String(v))));
    select.value = value == null ? '' : String(value);
  },
  sprintOptions(select, value, all = false) {
    this.options(select, [...(all ? [['all','All months'],['unscheduled','Unscheduled']] : [['','Unscheduled']]), ...this.sprints.map(s => [s.id,this.month(s.month)])], value);
  },
  initScope(onChange) {
    const select = document.getElementById('sprint-filter');
    const now = new Date();
    const month = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`;
    const fallback = String(this.sprints.find(s => s.month === month)?.id || 'unscheduled');
    let saved;
    try { saved = localStorage.getItem('ignatious-sprint'); } catch {}
    const requested = new URLSearchParams(location.search).get('sprint') || saved || fallback;
    this.scope = ['all','unscheduled',...this.sprints.map(s=>String(s.id))].includes(requested) ? requested : fallback;
    this.sprintOptions(select,this.scope,true);
    select.onchange = () => { this.setScope(select.value); this.run(onChange); };
    this.setScope(this.scope);
  },
  setScope(scope) {
    this.scope = String(scope);
    try { localStorage.setItem('ignatious-sprint',this.scope); } catch {}
    const url = new URL(location.href); url.searchParams.set('sprint',this.scope); history.replaceState(null,'',url);
    document.querySelectorAll('[data-board-link]').forEach(a => a.href = `/static/index.html?sprint=${encodeURIComponent(this.scope)}`);
    document.querySelectorAll('[data-plan-link]').forEach(a => a.href = `/static/backlog.html?sprint=${encodeURIComponent(this.scope)}`);
  },
  async roots() {
    const params = new URLSearchParams({roots_only:'true',project_id:'1'});
    if (this.scope === 'unscheduled') params.set('unscheduled','true');
    else if (this.scope !== 'all') params.set('sprint_id',this.scope);
    return this.api(`/api/tasks/?${params}`);
  },
  summary(tasks) {
    const s = this.sprints.find(s => String(s.id) === this.scope);
    const title = this.scope === 'all' ? 'All months' : s ? this.month(s.month) : 'Unscheduled';
    document.getElementById('scope-summary').textContent = `${title} · ${tasks.length} top-level tasks · ${tasks.filter(t=>t.status==='Complete').length} complete`;
    document.getElementById('sprint-goal').textContent = s?.goal || (s ? 'No sprint goal yet.' : 'Assign tasks to a month in Planning to focus your board.');
    const edit = document.getElementById('edit-sprint');
    if (edit) edit.disabled = !s;
  },
  taskLink(task) { return `/static/task.html?id=${task.id}&sprint=${encodeURIComponent(this.scope)}`; },
  field(label, select) { const l = this.el('label',label); select.setAttribute('aria-label',label); l.append(select); return l; },
  epicColor(epic) { return /^#[\da-f]{6}$/i.test(epic.color) ? epic.color : '#48d597'; },
  epicLabel(epic) {
    const label = this.el('span',epic.title,'epic-label');
    label.style.setProperty('--epic-color',this.epicColor(epic));
    return label;
  },
  card(task, refresh) {
    const card = this.el('article',null,'task-card'); card.dataset.taskId = task.id;
    const header = this.el('div',null,'task-card-header');
    const title = this.el('h3',null,'task-card-title'); const link = this.el('a',task.title); link.href = this.taskLink(task); title.append(link);
    header.append(title); card.append(header);
    const epic = this.epics.find(e=>e.id===task.epic_id);
    if(epic) card.append(this.epicLabel(epic));
    card.append(this.el('p',`#${task.id} · ${task.assignee || 'Unassigned'}`,'task-card-meta'));
    card.append(this.el('p',this.sprintName(task.sprint_id),'card-sprint'));
    if(task.resolution_state!=='Unresolved') card.append(this.el('p',`Decision: ${task.resolution_state}`,'resolution-badge'));
    if(task.open_needed_task_count) card.append(this.el('p',`${task.open_needed_task_count} needed items awaiting resolution`,'task-progress'));
    if(task.child_count) card.append(this.el('p',`${task.completed_children}/${task.child_count} direct subtasks complete · ${task.completed_descendants}/${task.descendant_count} across all levels`,'task-progress'));
    const fields = this.el('div',null,'card-fields');
    const status = this.el('select'); this.options(status,this.statuses.map(s=>[s,s]),task.status);
    status.onchange=()=>this.run(async()=>{ status.disabled=true; try{await this.api(`/api/tasks/${task.id}`,'PATCH',{status:status.value,expected_revision:task.revision});await refresh();}finally{status.disabled=false;status.value=task.status;} });
    fields.append(this.field('Status',status));
    const assignee = this.el('select');
    const names = [...new Set([...this.users.map(u=>u.name),...(task.assignee ? [task.assignee] : [])])];
    this.options(assignee,[['','Unassigned'],...names.map(n=>[n,n])],task.assignee);
    assignee.onchange=()=>this.run(async()=>{ assignee.disabled=true; try{await this.api(`/api/tasks/${task.id}`,'PATCH',{assignee:assignee.value||null,expected_revision:task.revision});await refresh();}finally{assignee.disabled=false;assignee.value=task.assignee||'';} });
    fields.append(this.field('Assignee',assignee)); card.append(fields);
    const actions = this.el('div',null,'task-card-actions');
    const open = this.el('a',task.child_count ? 'Open subtask board →' : 'Open task →','secondary-button'); open.href=this.taskLink(task);
    actions.append(open);card.append(actions);return card;
  },
  board(tasks, refresh) {
    const board = document.getElementById('board'); board.replaceChildren();
    for(const status of this.statuses) {
      const column=this.el('section',null,'kanban-column'); column.dataset.status=status;
      const header=this.el('div',null,'column-header');
      const members=tasks.filter(t=>t.status===status);
      header.append(this.el('h2',status),this.el('span',members.length,'count'));
      const body=this.el('div',null,'column-body');
      if(!members.length) body.append(this.el('p','No tasks here.','empty-state'));
      members.forEach(t=>body.append(this.card(t,refresh)));column.append(header,body);board.append(column);
    }
  },
  async formDialog(title, fields, submitLabel, action, extra) {
    const dialog=this.el('dialog');const form=this.el('form');
    const heading=this.el('h2',title);heading.id='dialog-heading';dialog.setAttribute('aria-labelledby',heading.id);form.append(heading);
    const controls={};
    fields.forEach(f=>{const wrap=this.el('div',null,'field');const input=this.el(f.options?'select':f.type==='textarea'?'textarea':'input');input.id=`dialog-${f.name}`;input.name=f.name;if(f.options)this.options(input,f.options.map(o=>Array.isArray(o)?o:[o,o]),f.value);else if(f.type!=='textarea')input.type=f.type||'text';if(f.required)input.required=true;if(f.max)input.maxLength=f.max;input.value=f.value??(f.options?(Array.isArray(f.options[0])?f.options[0][0]:f.options[0]):'');const label=this.el('label',f.label);label.htmlFor=input.id;wrap.append(label,input);form.append(wrap);controls[f.name]=input;});
    const error=this.el('p',null,'field-help');error.setAttribute('role','alert');form.append(error);
    const actions=this.el('div',null,'dialog-actions');const cancel=this.el('button','Cancel','secondary-button');cancel.type='button';cancel.onclick=()=>dialog.close();
    const submit=this.el('button',submitLabel,'primary-button');submit.type='submit';actions.append(cancel,submit);form.append(actions);
    if(extra){const button=this.el('button',extra.label,'secondary-button danger-button');button.type='button';button.onclick=async()=>{try{await extra.action();dialog.close();}catch(e){error.textContent=e.message;}};form.append(button);}
    form.onsubmit=async e=>{e.preventDefault();submit.disabled=true;error.textContent='';try{await action(Object.fromEntries(Object.entries(controls).map(([k,v])=>[k,v.value])));dialog.close();}catch(e){error.textContent=e.message;}finally{submit.disabled=false;}};
    dialog.append(form);document.body.append(dialog);dialog.addEventListener('close',()=>dialog.remove());dialog.showModal();
  },
  newTask(parent, refresh) {
    return this.formDialog(parent ? 'Add subtask' : 'Add task',[
      {name:'title',label:'Title',required:true,max:300},
      {name:'description',label:'Description',type:'textarea'}
    ],'Create task',async values=>{
      const body={...values,status:'Backlog',project_id:parent?.project_id||1};
      if(parent) body.parent_id=parent.id;
      else body.sprint_id=['all','unscheduled'].includes(this.scope)?null:Number(this.scope);
      await this.api('/api/tasks/','POST',body);await refresh();this.message('Task created.');
    });
  },
  sprintDialog(refresh, sprint) {
    const now=new Date(); const month=`${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`;
    const fields=[...(sprint?[]:[{name:'month',label:'Month',type:'month',value:month,required:true}]),{name:'goal',label:'Sprint goal',type:'textarea',value:sprint?.goal,max:3000}];
    this.formDialog(sprint?`Edit ${this.month(sprint.month)}`:'Plan a monthly sprint',fields,sprint?'Save goal':'Create sprint',async values=>{
      const result=await this.api(sprint?`/api/sprints/${sprint.id}`:'/api/sprints/',sprint?'PATCH':'POST',values);
      await this.refs();this.scope=String(result.id);this.sprintOptions(document.getElementById('sprint-filter'),this.scope,true);this.setScope(this.scope);await refresh();this.message(sprint?'Sprint updated.':'Sprint created. Use Planning to assign existing tasks.');
    },sprint?{label:'Delete empty sprint',action:async()=>{
      if(!confirm('Delete this empty sprint?'))return;
      await this.api(`/api/sprints/${sprint.id}`,'DELETE');await this.refs();this.setScope('unscheduled');this.sprintOptions(document.getElementById('sprint-filter'),this.scope,true);await refresh();
    }}:null);
  }
};
