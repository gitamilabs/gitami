import React, { useState, useEffect } from 'react';
import { getUserList } from './UserService.js';
import { Header } from './Header.jsx';

const Dashboard = () => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        getUserList().then(data => {
            setUsers(data);
            setLoading(false);
        });
    }, []);

    return (
        <div>
            <Header title="User Dashboard" />
            {loading ? <p>Loading...</p> : (
                <ul>
                    {users.map(u => <li key={u}>{u}</li>)}
                </ul>
            )}
        </div>
    );
};

export default Dashboard;
