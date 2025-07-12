#!/usr/bin/env python3
import json
import sys

def update_task_status(task_id, new_status):
    with open('tasks/tasks.json', 'r') as f:
        data = json.load(f)
    
    for task in data['master']['tasks']:
        if task['id'] == task_id:
            task['status'] = new_status
            break
    
    with open('tasks/tasks.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Task {task_id} updated to {new_status}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python update_task_status.py <task_id> <new_status>")
        sys.exit(1)
    
    task_id = int(sys.argv[1])
    new_status = sys.argv[2]
    update_task_status(task_id, new_status)