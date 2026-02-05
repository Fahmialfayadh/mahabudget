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

document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const loginBtn = document.getElementById('loginBtn');
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    loginBtn.disabled = true;
    loginBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Memproses...';

    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (response.ok) {
            window.location.href = '/';
        } else {
            showError(data.detail || 'Login gagal');
            loginBtn.disabled = false;
            loginBtn.innerHTML = '<span>Masuk</span><i class="bi bi-arrow-right"></i>';
        }
    } catch (error) {
        showError('Terjadi kesalahan. Coba lagi.');
        loginBtn.disabled = false;
        loginBtn.innerHTML = '<span>Masuk</span><i class="bi bi-arrow-right"></i>';
    }
});

function showError(message) {
    // Remove existing error if any
    const existingError = document.querySelector('.auth-error');
    if (existingError) {
        existingError.remove();
    }

    const errorDiv = document.createElement('div');
    errorDiv.className = 'auth-error';
    errorDiv.innerHTML = `<i class="bi bi-exclamation-circle"></i><span>${message}</span>`;

    const form = document.getElementById('loginForm');
    form.parentNode.insertBefore(errorDiv, form);
}