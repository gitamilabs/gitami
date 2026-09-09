import { fetchUsers, fetchUserById } from './api.js';

export function formatUser(user) {
    return `${user.name} <${user.email}>`;
}

export async function getUserList() {
    const users = await fetchUsers();
    return users.map(formatUser);
}

export async function getUserProfile(id) {
    const user = await fetchUserById(id);
    return formatUser(user);
}
