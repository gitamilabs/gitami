import React, { useState } from 'react';

export const Header = ({ title }) => {
    const [open, setOpen] = useState(false);
    return (
        <header>
            <h1>{title}</h1>
        </header>
    );
};
