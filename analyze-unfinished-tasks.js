const fs = require('fs');

// Read tasks.json
const tasksData = JSON.parse(fs.readFileSync('./tasks/tasks.json', 'utf8'));
const tasks = tasksData.master.tasks;

// Get unfinished tasks
const unfinishedTasks = tasks.filter(task => task.status === 'pending' || task.status === 'in_progress');

// Sort by priority
const priorityOrder = { high: 1, medium: 2, low: 3 };
unfinishedTasks.sort((a, b) => {
  const priorityA = priorityOrder[a.priority || 'medium'];
  const priorityB = priorityOrder[b.priority || 'medium'];
  if (priorityA !== priorityB) return priorityA - priorityB;
  return a.id - b.id;
});

console.log('# DETAILED UNFINISHED TASKS REPORT\n');
console.log(`Total Unfinished Tasks: ${unfinishedTasks.length}\n`);

// Group by priority
const highPriority = unfinishedTasks.filter(t => t.priority === 'high');
const mediumPriority = unfinishedTasks.filter(t => t.priority === 'medium');

console.log('## 🔴 HIGH PRIORITY UNFINISHED TASKS\n');
highPriority.forEach(task => {
  console.log(`### Task ${task.id}: ${task.title}\n`);
  console.log(`**Status**: ${task.status}`);
  console.log(`**Priority**: ${task.priority}`);
  
  if (task.dependencies && task.dependencies.length > 0) {
    console.log(`**Dependencies**: ${task.dependencies.join(', ')}`);
  }
  
  console.log(`\n**Description**:\n${task.description}\n`);
  
  if (task.details) {
    console.log(`**Implementation Details**:\n${task.details}\n`);
  }
  
  if (task.testStrategy) {
    console.log(`**Test Strategy**:\n${task.testStrategy}\n`);
  }
  
  if (task.subtasks && task.subtasks.length > 0) {
    console.log(`**Subtasks** (${task.subtasks.length} total):`);
    task.subtasks.forEach(subtask => {
      console.log(`\n#### ${task.id}.${subtask.id}: ${subtask.title}`);
      console.log(`- Status: ${subtask.status}`);
      if (subtask.dependencies && subtask.dependencies.length > 0) {
        console.log(`- Dependencies: ${subtask.dependencies.join(', ')}`);
      }
      if (subtask.description) {
        console.log(`- Description: ${subtask.description}`);
      }
      if (subtask.details) {
        console.log(`- Details: ${subtask.details}`);
      }
    });
  }
  
  console.log('\n---\n');
});

console.log('## 🟡 MEDIUM PRIORITY UNFINISHED TASKS\n');
mediumPriority.forEach(task => {
  console.log(`### Task ${task.id}: ${task.title}\n`);
  console.log(`**Status**: ${task.status}`);
  console.log(`**Priority**: ${task.priority}`);
  
  if (task.dependencies && task.dependencies.length > 0) {
    console.log(`**Dependencies**: ${task.dependencies.join(', ')}`);
  }
  
  console.log(`\n**Description**:\n${task.description}\n`);
  
  console.log('\n---\n');
});

// Create dependency graph
console.log('## 📊 DEPENDENCY ANALYSIS\n');
console.log('Tasks that can be started immediately (no pending dependencies):');
unfinishedTasks.forEach(task => {
  if (!task.dependencies || task.dependencies.length === 0) {
    console.log(`- Task ${task.id}: ${task.title}`);
  } else {
    const pendingDeps = task.dependencies.filter(dep => {
      const depTask = tasks.find(t => t.id == dep);
      return depTask && depTask.status === 'pending';
    });
    if (pendingDeps.length === 0) {
      console.log(`- Task ${task.id}: ${task.title}`);
    }
  }
});