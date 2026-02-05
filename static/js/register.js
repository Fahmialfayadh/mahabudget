function togglePassword() {
    const passwordInput = document.getElementById('password');
    const toggleIcon = document.getElementById('toggleIcon');

    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        toggleIcon.classList.remove('bi-eye');
        toggleIcon.classList.add('bi-eye-slash');
    } else {
        passwordInput.type = 'password';
        toggleIcon.classList.remove('bi-eye-slash');
        toggleIcon.classList.add('bi-eye');
    }
}

// Password strength checker
document.getElementById('password').addEventListener('input', (e) => {
    const password = e.target.value;
    const strengthBar = document.getElementById('strengthBar');
    const strengthHint = document.getElementById('strengthHint');

    strengthBar.className = 'password-strength-bar';

    if (password.length === 0) {
        strengthHint.textContent = 'Password minimal 6 karakter';
        return;
    }

    if (password.length < 6) {
        strengthBar.classList.add('weak');
        strengthHint.textContent = 'Terlalu pendek';
        return;
    }

    // Check strength
    let strength = 0;
    if (password.length >= 8) strength++;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++;
    if (/\d/.test(password)) strength++;
    if (/[^a-zA-Z0-9]/.test(password)) strength++;

    if (strength <= 1) {
        strengthBar.classList.add('weak');
        strengthHint.textContent = 'Password lemah';
    } else if (strength <= 2) {
        strengthBar.classList.add('medium');
        strengthHint.textContent = 'Password sedang';
    } else {
        strengthBar.classList.add('strong');
        strengthHint.textContent = 'Password kuat';
    }
});

document.getElementById('registerForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const registerBtn = document.getElementById('registerBtn');
    const fullName = document.getElementById('fullName').value;
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    registerBtn.disabled = true;
    registerBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Memproses...';

    try {
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                email,
                password,
                full_name: fullName
            })
        });

        const data = await response.json();

        if (response.ok) {
            window.location.href = '/';
        } else {
            showError(data.detail || 'Registrasi gagal');
            registerBtn.disabled = false;
            registerBtn.innerHTML = '<span>Daftar Sekarang</span><i class="bi bi-arrow-right"></i>';
        }
    } catch (error) {
        showError('Terjadi kesalahan. Coba lagi.');
        registerBtn.disabled = false;
        registerBtn.innerHTML = '<span>Daftar Sekarang</span><i class="bi bi-arrow-right"></i>';
    }
});

function showError(message) {
    // Remove existing messages if any
    const existingError = document.querySelector('.auth-error');
    if (existingError) {
        existingError.remove();
    }

    const errorDiv = document.createElement('div');
    errorDiv.className = 'auth-error';
    errorDiv.innerHTML = `<i class="bi bi-exclamation-circle"></i><span>${message}</span>`;

    const form = document.getElementById('registerForm');
    form.parentNode.insertBefore(errorDiv, form);
}