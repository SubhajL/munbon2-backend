const fs = require('fs');

// Read tasks.json
const tasksData = JSON.parse(fs.readFileSync('./tasks/tasks.json', 'utf8'));
const tasks = tasksData.master.tasks;

// Get unfinished tasks
const unfinishedTasks = tasks.filter(task => task.status === 'pending' || task.status === 'in_progress');

// Sort by priority and dependencies
const priorityOrder = { high: 1, medium: 2, low: 3 };
unfinishedTasks.sort((a, b) => {
  const priorityA = priorityOrder[a.priority || 'medium'];
  const priorityB = priorityOrder[b.priority || 'medium'];
  if (priorityA !== priorityB) return priorityA - priorityB;
  
  // Then sort by number of dependencies (fewer deps first)
  const depsA = (a.dependencies || []).length;
  const depsB = (b.dependencies || []).length;
  if (depsA !== depsB) return depsA - depsB;
  
  return a.id - b.id;
});

console.log('# UNFINISHED TASKS - COMPLETE DETAILS\n');
console.log(`Total: ${unfinishedTasks.length} tasks\n`);

// Categorize by readiness
const readyToStart = [];
const waitingForDeps = [];

unfinishedTasks.forEach(task => {
  const pendingDeps = (task.dependencies || []).filter(dep => {
    const depTask = tasks.find(t => t.id == dep);
    return depTask && depTask.status === 'pending';
  });
  
  if (pendingDeps.length === 0) {
    readyToStart.push(task);
  } else {
    waitingForDeps.push({ ...task, pendingDeps });
  }
});

console.log('## 🚀 READY TO START (All dependencies completed)\n');
readyToStart.forEach(task => {
  console.log(`### ${task.id}. ${task.title} [${task.priority.toUpperCase()}]`);
  console.log(`Dependencies: ${task.dependencies?.join(', ') || 'None'}`);
  console.log(`Description: ${task.description}`);
  if (task.subtasks?.length > 0) {
    console.log(`Subtasks: ${task.subtasks.length}`);
  }
  console.log('');
});

console.log('\n## ⏸️ WAITING FOR DEPENDENCIES\n');
waitingForDeps.forEach(({ pendingDeps, ...task }) => {
  console.log(`### ${task.id}. ${task.title} [${task.priority.toUpperCase()}]`);
  console.log(`Waiting for tasks: ${pendingDeps.join(', ')}`);
  console.log(`Description: ${task.description}`);
  console.log('');
});

// Output full details for each task
console.log('\n## 📋 FULL TASK DETAILS\n');
unfinishedTasks.forEach(task => {
  console.log(`${'='.repeat(80)}`);
  console.log(`TASK ${task.id}: ${task.title}`);
  console.log(`${'='.repeat(80)}\n`);
  
  console.log(`**Priority**: ${task.priority}`);
  console.log(`**Status**: ${task.status}`);
  console.log(`**Dependencies**: ${task.dependencies?.join(', ') || 'None'}\n`);
  
  console.log(`**Description**:`);
  console.log(task.description);
  console.log('');
  
  if (task.details) {
    console.log(`**Implementation Details**:`);
    console.log(task.details);
    console.log('');
  }
  
  if (task.testStrategy) {
    console.log(`**Test Strategy**:`);
    console.log(task.testStrategy);
    console.log('');
  }
  
  if (task.subtasks && task.subtasks.length > 0) {
    console.log(`**Subtasks (${task.subtasks.length}):**`);
    task.subtasks.forEach((st, idx) => {
      console.log(`\n${idx + 1}. ${st.title}`);
      console.log(`   Status: ${st.status}`);
      if (st.dependencies?.length > 0) {
        console.log(`   Dependencies: ${st.dependencies.join(', ')}`);
      }
      if (st.description) {
        console.log(`   Description: ${st.description}`);
      }
    });
    console.log('');
  }
  
  console.log('\n');
});