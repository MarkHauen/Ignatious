const taskId=Number(new URLSearchParams(location.search).get('id'));
const $=id=>document.getElementById(id);
let task, allTasks=[], dirty=false, editorRevision;
function parentSprint() {
  const parent=allTasks.find(t=>t.id===Number($('parent').value));
  $('task-sprint').disabled=Boolean(parent);
  if(parent)$('task-sprint').value=parent.sprint_id??'';
  $('sprint-help').textContent=parent?'Inherited from the parent. Move the top-level task to change this branch’s sprint.':'Moving this task to a sprint moves all of its subtasks too.';
}
async function loadEditor() {
  await I.refs();
  [task,allTasks]=await Promise.all([I.api(`/api/tasks/${taskId}`),I.api('/api/tasks/')]);
  const trail=await I.api(`/api/tasks/${taskId}/ancestors`);
  I.scope=new URLSearchParams(location.search).get('sprint') || String(task.sprint_id||'unscheduled');
  I.setScope(I.scope);
  $('breadcrumbs').replaceChildren();
  const board=I.el('a','Monthly board');board.href=`/static/index.html?sprint=${encodeURIComponent(I.scope)}`;$('breadcrumbs').append(board);
  trail.forEach(t=>{const a=I.el('a',t.title);a.href=I.taskLink(t);$('breadcrumbs').append(I.el('span','/'),a);});
  const current=I.el('span',task.title);current.setAttribute('aria-current','page');$('breadcrumbs').append(I.el('span','/'),current);
  document.title=`${task.title} · Ignatious`;$('page-title').textContent=task.title;$('page-title').className='task-detail-title';
  editorRevision=task.revision;
  $('resolution-state').value=task.resolution_state; $('resolution').value=task.resolution||''; $('review-notes').value=task.review_notes||'';
  $('title').value=task.title;$('description').value=task.description||'';
  I.options($('status'),I.statuses.map(s=>[s,s]),task.status);
  const names=[...new Set([...I.users.map(u=>u.name),...(task.assignee?[task.assignee]:[])])];
  I.options($('assignee'),[['','Unassigned'],...names.map(n=>[n,n])],task.assignee);
  I.options($('epic'),[['','No epic'],...I.epics.filter(e=>e.project_id===task.project_id).map(e=>[e.id,e.title])],task.epic_id);
  const excluded=new Set([task.id]);let changed=true;
  while(changed){changed=false;allTasks.forEach(t=>{if(excluded.has(t.parent_id)&&!excluded.has(t.id)){excluded.add(t.id);changed=true;}});}
  I.options($('parent'),[['','Top-level task'],...allTasks.filter(t=>t.project_id===task.project_id&&!excluded.has(t.id)).map(t=>[t.id,`#${t.id} · ${t.title}`])],task.parent_id);
  I.sprintOptions($('task-sprint'),task.sprint_id);parentSprint();
  $('task-form').hidden=false;$('new-subtask').disabled=false;dirty=false;await loadChildren();await loadNeeds();
}
async function loadChildren() {
  const [children,current]=await Promise.all([I.api(`/api/tasks/?parent_id=${taskId}`),I.api(`/api/tasks/${taskId}`)]);
  task=current;I.board(children,loadChildren);
  $('subtask-progress').textContent=`${task.completed_children}/${task.child_count} direct subtasks complete · ${task.completed_descendants}/${task.descendant_count} across all levels. Open any subtask to go deeper.`;
  $('delete-task').disabled=task.child_count>0||task.needed_task_count>0;
  $('delete-task').title=task.child_count?'Move or delete subtasks before deleting this task.':'';
}
$('parent').onchange=parentSprint;
$('task-form').addEventListener('input',()=>dirty=true);
$('task-form').addEventListener('change',()=>dirty=true);
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
$('task-form').onsubmit=e=>{e.preventDefault();I.run(async()=>{
  const button=$('save-task');button.disabled=true;
  try{
    const body={expected_revision:editorRevision,resolution_state:$('resolution-state').value,resolution:$('resolution').value||null,review_notes:$('review-notes').value||null,title:$('title').value,description:$('description').value,status:$('status').value,assignee:$('assignee').value||null,epic_id:$('epic').value?Number($('epic').value):null,parent_id:$('parent').value?Number($('parent').value):null};
    if(body.parent_id===null)body.sprint_id=$('task-sprint').value?Number($('task-sprint').value):null;
    await I.api(`/api/tasks/${taskId}`,'PATCH',body);dirty=false;await loadEditor();I.message('Task saved.');
  }finally{button.disabled=false;}
});};
$('new-subtask').onclick=()=>I.newTask(task,loadChildren);
$('delete-task').onclick=()=>I.run(async()=>{if(!confirm(`Delete "${task.title}"?`))return;await I.api(`/api/tasks/${taskId}`,'DELETE');dirty=false;location.href=task.parent_id?I.taskLink({id:task.parent_id}):`/static/index.html?sprint=${encodeURIComponent(I.scope)}`;});
I.run(async()=>{if(!Number.isInteger(taskId)||taskId<=0)throw new Error('Choose a valid task from the board.');await loadEditor();});

async function loadNeeds() {
  const needs=await I.api(`/api/needed-tasks/?task_id=${taskId}`);
  N.render($('needed-list'),needs,async()=>{await loadNeeds();await loadChildren();});
  $('add-needed').disabled=false;
}
$('add-needed').onclick=()=>N.edit(null,taskId,async()=>{await loadNeeds();await loadChildren();});
