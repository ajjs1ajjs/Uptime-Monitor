let currentUser = null;
let lastUsersList = [];
loadUsers();
loadCurrentUser();

async function loadCurrentUser() {
    try { const r = await fetch('/api/user'); if (r.ok) { currentUser = await r.json(); if (!currentUser.is_admin) window.location.href='/'; } else { window.location.href='/login'; } } catch(e) { console.error(e); }
}
async function loadUsers() {
    try { const r = await fetch('/api/users'); if (!r.ok) { document.getElementById('usersTableBody').innerHTML = '<tr><td colspan="6" class="text-center p-8 text-red-400">Error loading users</td></tr>'; return; } const users = await r.json(); lastUsersList = users; renderUsers(users); } catch(e) { document.getElementById('usersTableBody').innerHTML = '<tr><td colspan="6" class="text-center p-8 text-red-400">Error loading users</td></tr>'; }
}
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function renderUsers(users) {
    const tbody = document.getElementById('usersTableBody');
    if (users.length === 0) { tbody.innerHTML = '<tr><td colspan="6" class="text-center p-8 text-slate-500">No users</td></tr>'; return; }
    
    const lang = localStorage.getItem('lang') || 'uk';
    const dict = i18n[lang] || i18n.uk;

    tbody.innerHTML = users.map(u => {
        const safeUser = escapeHtml(u.username);
        return `<tr class="border-b border-slate-700/30 hover:bg-white/[0.02]">
        <td class="p-4 text-sm">${u.id}</td>
        <td class="p-4 text-sm font-medium">${escapeHtml(u.username)}</td>
        <td class="p-4"><span class="px-3 py-1 rounded-full text-xs font-semibold ${u.role === 'admin' ? 'bg-accent/10 text-accent' : 'bg-slate-500/10 text-slate-400'}">${escapeHtml(u.role)}</span></td>
        <td class="p-4 text-sm text-slate-400 hidden md:table-cell">${formatDate(u.created_at)}</td>
        <td class="p-4 text-sm text-slate-400 hidden md:table-cell">${u.last_login ? formatDate(u.last_login) : 'Never'}</td>
        <td class="p-4"><div class="flex gap-2">
            <button data-action="showEditModal" data-username="${escapeHtml(u.username)}" data-role="${escapeHtml(u.role)}" class="px-3 py-1.5 rounded-lg bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 transition text-xs font-medium">${dict.card_edit || 'Edit'}</button>
            ${u.username !== currentUser?.username ? `<button data-action="deleteUser" data-username="${escapeHtml(u.username)}" class="px-3 py-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition text-xs font-medium">${dict.card_delete || 'Delete'}</button>` : ''}
        </div></td>
    </tr>`}).join('');
}
function formatDate(d) { if (!d) return 'Never'; try { return new Date(d).toLocaleDateString('uk-UA', {year:'numeric',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}); } catch { return d; } }
function showCreateModal() { document.getElementById('newUsername').value=''; document.getElementById('newPassword').value=''; document.getElementById('newRole').value='viewer'; document.getElementById('createModal').classList.remove('hidden'); document.getElementById('createModal').classList.add('flex'); }
function showEditModal(u, r) { document.getElementById('editUsername').value=u; document.getElementById('editRole').value=r; document.getElementById('editPassword').value=''; document.getElementById('editModal').classList.remove('hidden'); document.getElementById('editModal').classList.add('flex'); }
function closeModal(id) { document.getElementById(id).classList.add('hidden'); document.getElementById(id).classList.remove('flex'); }
async function createUser() {
    const username = document.getElementById('newUsername').value.trim();
    const password = document.getElementById('newPassword').value;
    const role = document.getElementById('newRole').value;
    if (!username || !password) return alert('Ім\'я та пароль обов\'язкові');
    try { const r = await fetch('/api/users', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username,password,role})}); const d = await r.json(); if (r.ok) { alert(d.message); closeModal('createModal'); loadUsers(); } else { alert(d.detail || 'Error'); } } catch(e) { alert('Error creating user'); }
}
async function updateUser() {
    const username = document.getElementById('editUsername').value;
    const role = document.getElementById('editRole').value;
    const password = document.getElementById('editPassword').value;
    try { const body = {role}; if (password) body.password = password; const r = await fetch('/api/users/' + username, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}); const d = await r.json(); if (r.ok) { alert(d.message); closeModal('editModal'); loadUsers(); } else { alert(d.detail || 'Error'); } } catch(e) { alert('Error updating user'); }
}
async function deleteUser(username) {
    if (!confirm('Delete user "' + username + '"?')) return;
    try { const r = await fetch('/api/users/' + username, {method:'DELETE'}); const d = await r.json(); if (r.ok) { alert(d.message); loadUsers(); } else { alert(d.detail || 'Error'); } } catch(e) { alert('Error deleting user'); }
}


// --- delegated action handlers for the users page ---
window.AppActions = Object.assign(window.AppActions || {}, {
  showCreateModal: () => showCreateModal(),
  createUser: () => createUser(),
  updateUser: () => updateUser(),
  closeModal: (el) => closeModal(el.dataset.modal),
  showEditModal: (el) => showEditModal(el.dataset.username, el.dataset.role),
  deleteUser: (el) => deleteUser(el.dataset.username),
});
