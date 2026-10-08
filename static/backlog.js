let tasks = [], selected = new Set();
const $ = id => document.getElementById(id);
function visible() {
  const q=$('search').value.toLowerCase(), status=$('status-filter').value, epic=$('epic-filter').value;
  return tasks.filter(t=>(!status||t.status===status)&&(!epic||String(t.epic_id)===epic)&&[t.title,t.description,t.assignee,t.resolution,t.review_notes].some(v=>(v||'').toLowerCase().includes(q)));
}
function selection() {
  const rows=visible();const ids=new Set(rows.map(t=>t.id));selected=new Set([...selected].filter(id=>ids.has(id)));
  $('selection-count').textContent=`${selected.size} selected`;$('assign').disabled=!selected.size;
  $('select-all').checked=rows.length>0&&rows.every(t=>selected.has(t.id));
  $('select-all').indeterminate=selected.size>0&&!$('select-all').checked;
}
function render() {
  selection();const list=$('planning-list');list.replaceChildren();
  const rows=visible();
  if(!rows.length)list.append(I.el('p','No tasks match this view. Choose another month or add a task.','empty-state'));
  rows.forEach(task=>{
    const row=I.el('article',null,'planning-row');row.dataset.taskId=task.id;
    const check=I.el('input');check.type='checkbox';check.checked=selected.has(task.id);check.setAttribute('aria-label',`Select ${task.title}`);check.onchange=()=>{if(check.checked)selected.add(task.id);else selected.delete(task.id);selection();};
    const main=I.el('div');const h=I.el('h3');const a=I.el('a',task.title);a.href=I.taskLink(task);h.append(a);main.append(h);
    const epic=I.epics.find(e=>e.id===task.epic_id);
    const labels=I.el('div',null,'planning-row-labels');
    const status=I.el('span',task.status,'task-status-label');status.dataset.status=task.status;labels.append(status);
    if(epic) labels.append(I.epicLabel(epic));
    main.append(labels,I.el('p',`#${task.id} · ${task.assignee||'Unassigned'}`));
    if(task.descendant_count)main.append(I.el('p',`${task.completed_descendants}/${task.descendant_count} nested tasks complete; this branch moves together.`));
    const sprint=I.el('select');I.sprintOptions(sprint,task.sprint_id);
    sprint.onchange=()=>I.run(async()=>{sprint.disabled=true;try{await I.api(`/api/tasks/${task.id}`,'PATCH',{sprint_id:sprint.value?Number(sprint.value):null});await load();I.message('Task branch moved.');}finally{sprint.disabled=false;sprint.value=task.sprint_id??'';}});
    const field=I.field('Monthly sprint',sprint);field.className='field';row.append(check,main,field);list.append(row);
  });
}
function renderEpics() {
  const list=$('epic-list');list.replaceChildren();
  I.epics.forEach(epic=>{
    const e=I.el('article',null,'epic-card');e.style.setProperty('--epic-color',I.epicColor(epic));
    const h=I.el('div',null,'epic-card-header');
    const color=I.el('input',null,'epic-color-input');color.type='color';color.value=I.epicColor(epic);color.setAttribute('aria-label',`Color for ${epic.title}`);color.title=`Color for ${epic.title}`;
    color.onchange=()=>I.run(async()=>{color.disabled=true;try{await I.api(`/api/epics/${epic.id}`,'PATCH',{color:color.value});await refreshRefs();render();}finally{color.disabled=false;color.value=I.epicColor(epic);}});
    h.append(color,I.el('h3',epic.title,'epic-card-title'));
    const del=I.el('button','×','icon-button');del.setAttribute('aria-label',`Delete epic ${epic.title}`);del.onclick=()=>I.run(async()=>{if(!confirm(`Delete epic "${epic.title}"? Tasks will remain.`))return;await I.api(`/api/epics/${epic.id}`,'DELETE');await refreshRefs();await load();});h.append(del);e.append(h,I.el('p',epic.description||'','epic-card-meta'));list.append(e);
  });
}
function epicFilterColor() {
  const epic=I.epics.find(epic=>String(epic.id)===$('epic-filter').value);
  $('epic-filter').style.setProperty('--epic-color',epic?I.epicColor(epic):'var(--line-bright)');
}
async function refreshRefs() {
  await I.refs();I.sprintOptions($('assign-sprint'),['all','unscheduled'].includes(I.scope)?'':I.scope);
  const epic=$('epic-filter').value;I.options($('epic-filter'),[['','All epics'],...I.epics.map(e=>[e.id,e.title])],I.epics.some(e=>String(e.id)===epic)?epic:'');epicFilterColor();renderEpics();
}
async function load() {tasks=await I.roots();selected.clear();await refreshRefs();I.summary(tasks);render();}
['search','status-filter','epic-filter'].forEach(id=>$(id).addEventListener(id==='search'?'input':'change',render));
$('epic-filter').addEventListener('change',epicFilterColor);
$('select-all').onchange=()=>{selected=$('select-all').checked?new Set(visible().map(t=>t.id)):new Set();render();};
$('assign').onclick=()=>I.run(async()=>{
  $('assign').disabled=true;
  try{await I.api('/api/tasks/assign-sprint','POST',{task_ids:[...selected],sprint_id:$('assign-sprint').value?Number($('assign-sprint').value):null});await load();I.message('Selected task branches moved.');}finally{selection();}
});
$('new-task').onclick=()=>I.newTask(null,load);
$('new-sprint').onclick=()=>I.sprintDialog(load);
$('edit-sprint').onclick=()=>I.sprintDialog(load,I.sprints.find(s=>String(s.id)===I.scope));
$('new-epic').onclick=()=>I.formDialog('Add epic',[{name:'title',label:'Title',required:true,max:300},{name:'description',label:'Description',type:'textarea'},{name:'color',label:'Epic color',type:'color',value:'#48d597'}],'Create epic',async data=>{await I.api('/api/epics/','POST',data);await load();});
I.run(async()=>{await I.refs();I.initScope(load);I.options($('status-filter'),[['','All statuses'],...I.statuses.map(s=>[s,s])],'');await load();['new-task','new-sprint','new-epic','sprint-filter'].forEach(id=>$(id).disabled=false);});
