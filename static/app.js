let tasks = [];
function render() {
  const q = document.getElementById('search').value.toLowerCase();
  I.board(tasks.filter(t => [t.title,t.description,t.assignee,t.resolution,t.review_notes].some(v => (v||'').toLowerCase().includes(q))),load);
}
async function load() { tasks = await I.roots(); I.summary(tasks); render(); }
document.getElementById('search').oninput = render;
document.getElementById('new-task').onclick = () => I.newTask(null,load);
document.getElementById('new-sprint').onclick = () => I.sprintDialog(load);
document.getElementById('edit-sprint').onclick = () => I.sprintDialog(load,I.sprints.find(s=>String(s.id)===I.scope));
I.run(async()=>{
  await I.refs();I.initScope(load);await load();
  ['new-task','new-sprint','sprint-filter'].forEach(id=>document.getElementById(id).disabled=false);
});
