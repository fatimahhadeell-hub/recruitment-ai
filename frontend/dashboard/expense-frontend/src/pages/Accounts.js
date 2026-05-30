import React, { useEffect, useState } from 'react';

const API = 'http://localhost:8081/api';

function Accounts() {
  const [accounts, setAccounts] = useState([]);
  const [form, setForm] = useState({ name: '', type: 'CASH', initialBalance: 0 });

  const load = () => fetch(`${API}/accounts`).then(r => r.json()).then(setAccounts).catch(() => {});
  useEffect(() => { load(); }, []);

  const submit = () => {
  fetch(`${API}/accounts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: form.name,
      type: form.type,
      initialBalance: parseFloat(form.initialBalance),
      currentBalance: parseFloat(form.initialBalance),
      isArchived: false,
      user: { id: 1 },
      currency: { code: 'USD' }
    })
  }).then(r => {
    if (r.ok) { load(); setForm({ name: '', type: 'CASH', initialBalance: 0 }); }
    else { r.text().then(t => console.log(t)); }
  });
};

  const del = (id) => fetch(`${API}/accounts/${id}`, { method: 'DELETE' }).then(load);

  return (
    <div className="page">
      <h2>Accounts</h2>
      <div className="form-card">
        <h3>Add Account</h3>
        <div className="form-row">
          <input placeholder="Account name" value={form.name} onChange={e => setForm({...form, name: e.target.value})} />
          <select value={form.type} onChange={e => setForm({...form, type: e.target.value})}>
            <option>CASH</option>
            <option>BANK</option>
            <option>CREDIT_CARD</option>
            <option>MOBILE_WALLET</option>
            <option>OTHER</option>
          </select>
          <input type="number" placeholder="Initial balance" value={form.initialBalance} onChange={e => setForm({...form, initialBalance: e.target.value})} />
          <button className="btn btn-primary" onClick={submit}>Add</button>
        </div>
      </div>
      <table>
        <thead><tr><th>Name</th><th>Type</th><th>Balance</th><th>Action</th></tr></thead>
        <tbody>
          {accounts.map(a => (
            <tr key={a.id}>
              <td>{a.name}</td>
              <td>{a.type}</td>
              <td>${a.currentBalance}</td>
              <td><button className="btn btn-danger" onClick={() => del(a.id)}>Delete</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default Accounts;