const API_BASE = 'https://api.example.com';

export async function fetchUsers() {
    const response = await fetch(`${API_BASE}/users`);
    return response.json();
}

export async function fetchUserById(id) {
    const response = await fetch(`${API_BASE}/users/${id}`);
    return response.json();
}

export async function createUser(userData) {
    const response = await fetch(`${API_BASE}/users`, {
        method: 'POST',
        body: JSON.stringify(userData),
    });
    return response.json();
}
