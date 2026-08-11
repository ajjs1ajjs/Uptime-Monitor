// Change-password form validation (no inline event attributes).
(function () {
  'use strict';
  const form = document.getElementById('changePasswordForm');
  if (!form) return;
  form.addEventListener('submit', function (e) {
    const newPass = document.getElementById('new_password').value;
    const confirmPass = document.getElementById('confirm_password').value;
    if (newPass !== confirmPass) { showToast('Passwords do not match!', true); e.preventDefault(); return; }
    if (newPass.length < 12) { showToast('Password must be at least 12 characters!', true); e.preventDefault(); return; }
    if (!/[A-Z]/.test(newPass)) { showToast('Password must contain at least one uppercase letter!', true); e.preventDefault(); return; }
    if (!/[a-z]/.test(newPass)) { showToast('Password must contain at least one lowercase letter!', true); e.preventDefault(); return; }
    if (!/[0-9]/.test(newPass)) { showToast('Password must contain at least one digit!', true); e.preventDefault(); return; }
  });
})();
