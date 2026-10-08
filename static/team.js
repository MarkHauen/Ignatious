const API = "/api/";

let allTasks = [];

// Edit modal state
let editingUserId = null;
let editingUserName = "";

async function loadUsers() {
  const tbody = document.getElementById("users-tbody");
  tbody.innerHTML = "<tr><td colspan='7' class='loading'>Loading...</td></tr>";

  try {
    const [usersRes, tasksRes] = await Promise.all([
      fetch(API + "users/"),
      fetch(API + "tasks/"),
    ]);
    const users = await usersRes.json();
    allTasks = await tasksRes.json();

    tbody.innerHTML = "";

    if (users.length === 0) {
      tbody.innerHTML =
        "<tr><td colspan='7' class='empty-state'>No team members yet. Add one above.</td></tr>";
      return;
    }

    const statuses = ["Backlog", "Ready for Action", "In Progress", "In Review"];

    users.forEach((user) => {
      const tr = document.createElement("tr");

      const counts = {};
      statuses.forEach((s) => {
        counts[s] = allTasks.filter((t) => t.assignee === user.name && t.status === s).length;
      });
      const total = Object.values(counts).reduce((a, b) => a + b, 0);

      tr.innerHTML = `
        <td class=profile-link data-id="${user.id}" data-name="${escapeHtml(user.name)}">${escapeHtml(user.name)}</td>
        <td class="task-count backlog-count">${counts["Backlog"]}</td>
        <td class="task-count ready-count">${counts["Ready for Action"]}</td>
        <td class="task-count progress-count">${counts["In Progress"]}</td>
        <td class="task-count review-count">${counts["In Review"]}</td>
        <td class="task-count total-count">${total}</td>
        <td>
          <button class="secondary-button edit-button" data-id="${user.id}" data-name="${escapeHtml(user.name)}">Edit</button>
          <button class="remove-button" data-id="${user.id}" data-name="${escapeHtml(user.name)}">
            Remove
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });

    // Wire up profile links
    tbody.querySelectorAll(".profile-link").forEach((btn) => {
      btn.addEventListener("click", () => openProfile(btn.dataset.id, btn.dataset.name));
    });

    // Wire up edit buttons
    tbody.querySelectorAll(".edit-button").forEach((btn) => {
      btn.addEventListener("click", () => openEdit(btn.dataset.id, btn.dataset.name));
    });

    // Wire up remove buttons
    tbody.querySelectorAll(".remove-button").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        const name = btn.dataset.name;
        if (!confirm(`Remove "${name}" from the team? All their tasks will be unassigned.`)) return;
        try {
          const res = await fetch(API + `users/${id}/`, { method: "DELETE" });
          if (res.ok) {
            showAddMessage(`"${name}" removed.`, "success");
            loadUsers();
          } else {
            const body = await res.json();
            showAddMessage(body.detail || "Failed to remove user.", "error");
          }
        } catch (e) {
          showAddMessage("Failed to remove user.", "error");
        }
      });
    });
  } catch (err) {
    tbody.innerHTML =
      "<tr><td colspan='7' class='error-state'>Failed to load team. Is the server running?</td></tr>";
  }
}

function showAddMessage(msg, type) {
  const el = document.getElementById("add-message");
  el.textContent = msg;
  el.className = "message " + type;
  setTimeout(() => {
    el.textContent = "";
    el.className = "message";
  }, 3000);
}

// Add user
document.getElementById("add-user-button").addEventListener("click", async () => {
  const nameInput = document.getElementById("new-user-name");
  const name = nameInput.value.trim();
  if (!name) {
    showAddMessage("Please enter a name.", "error");
    return;
  }
  try {
    const res = await fetch(API + "users/add/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (res.ok) {
      showAddMessage(`"${name}" added successfully!`, "success");
      nameInput.value = "";
      loadUsers();
    } else {
      const body = await res.json();
      showAddMessage(body.detail || "Failed to add user.", "error");
    }
  } catch (e) {
    showAddMessage("Failed to connect to server.", "error");
  }
});

document.getElementById("new-user-name").addEventListener("keypress", (e) => {
  if (e.key === "Enter") document.getElementById("add-user-button").click();
});

// Edit modal
function openEdit(userId, userName) {
  editingUserId = userId;
  editingUserName = userName;
  document.getElementById("edit-user-name").value = userName;
  document.getElementById("edit-modal-overlay").classList.add("show");
}

function closeEditModal() {
  document.getElementById("edit-modal-overlay").classList.remove("show");
  editingUserId = null;
  editingUserName = "";
}

document.getElementById("edit-cancel-button").addEventListener("click", closeEditModal);
document.getElementById("edit-modal-overlay").addEventListener("click", (e) => {
  if (e.target.id === "edit-modal-overlay") closeEditModal();
});

document.getElementById("edit-save-button").addEventListener("click", async () => {
  const newName = document.getElementById("edit-user-name").value.trim();
  if (!newName) {
    showAddMessage("Name cannot be empty.", "error");
    return;
  }
  if (newName === editingUserName) {
    closeEditModal();
    return;
  }
  try {
    const res = await fetch(API + `users/${editingUserId}/`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName }),
    });
    if (res.ok) {
      showAddMessage(`Renamed "${editingUserName}" → "${newName}".`, "success");
      closeEditModal();
      loadUsers();
    } else {
      const body = await res.json();
      showAddMessage(body.detail || "Failed to rename.", "error");
    }
  } catch (e) {
    showAddMessage("Failed to rename user.", "error");
  }
});

// Profile modal
function openProfile(userId, userName) {
  const userTasks = allTasks.filter((t) => t.assignee === userName);
  const statuses = ["Backlog", "Ready for Action", "In Progress", "In Review"];
  const counts = {};
  statuses.forEach((s) => {
    counts[s] = userTasks.filter((t) => t.status === s).length;
  });
  const total = userTasks.length;

  document.getElementById("profile-name").textContent = userName;
  document.getElementById("profile-backlog").textContent = counts["Backlog"];
  document.getElementById("profile-ready").textContent = counts["Ready for Action"];
  document.getElementById("profile-progress").textContent = counts["In Progress"];
  document.getElementById("profile-review").textContent = counts["In Review"];
  document.getElementById("profile-total").textContent = total;

  const taskList = document.getElementById("profile-tasks");
  if (userTasks.length === 0) {
    taskList.innerHTML = "<p class='empty-state'>No tasks assigned.</p>";
  } else {
    taskList.innerHTML = "";
    userTasks.forEach((t) => {
      const div = document.createElement("div");
      div.className = "profile-task-item";
      div.innerHTML = `
        <span class="status-badge">${t.status}</span>
        <span class="task-title">${escapeHtml(t.title)}</span>
      `;
      taskList.appendChild(div);
    });
  }

  document.getElementById("profile-modal-overlay").classList.add("show");
}

function closeProfileModal() {
  document.getElementById("profile-modal-overlay").classList.remove("show");
}

document.getElementById("profile-close-button").addEventListener("click", closeProfileModal);
document.getElementById("profile-modal-overlay").addEventListener("click", (e) => {
  if (e.target.id === "profile-modal-overlay") closeProfileModal();
});

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML.replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

window.addEventListener("DOMContentLoaded", loadUsers);
