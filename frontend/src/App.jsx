import { useState, useEffect } from 'react'

const API_BASE = "https://playto-pay-assignment-1.onrender.com/api/v1";

function App() {
  const [allMerchants, setAllMerchants] = useState([])
  const [merchant, setMerchant] = useState(null)
  const [transactions, setTransactions] = useState([])
  const [payouts, setPayouts] = useState([])

  const [amount, setAmount] = useState('')
  const [bankAccount, setBankAccount] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const fetchData = async () => {
    try {
      // 1. Fetch all merchants to populate the switcher and get balances
      const mRes = await fetch(`${API_BASE}/merchants/`)
      const mData = await mRes.json()
      const merchantsList = mData.results ? mData.results : mData

      if (!merchantsList || !merchantsList.length) return

      setAllMerchants(merchantsList)

      // 2. Determine which merchant to display
      let activeMerchant = merchant

      if (!activeMerchant) {
        // Default to first merchant on initial load
        activeMerchant = merchantsList[0]
        setMerchant(activeMerchant)
      } else {
        // Sync the current merchant to get the latest balance/held_balance
        const updated = merchantsList.find(m => m.id === activeMerchant.id)
        if (updated) {
          activeMerchant = updated
          setMerchant(updated)
        }
      }

      // 3. Fetch details for the active merchant
      const tRes = await fetch(`${API_BASE}/merchants/${activeMerchant.id}/transactions/`)
      const tData = await tRes.json()
      setTransactions(tData.results ? tData.results : tData)

      const pRes = await fetch(`${API_BASE}/merchants/${activeMerchant.id}/payouts/`)
      const pData = await pRes.json()
      setPayouts(pData.results ? pData.results : pData)

    } catch (err) {
      console.error("Error fetching data:", err)
    }
  }

  useEffect(() => {
    fetchData()
    // Poll for live status updates every 2 seconds
    const interval = setInterval(fetchData, 2000)
    return () => clearInterval(interval)
  }, [merchant?.id]) // Re-run if we manually switch merchants

  const handlePayout = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    if (!merchant) return

    try {
      const amountPaise = Math.round(parseFloat(amount) * 100)

      const res = await fetch(`${API_BASE}/payouts/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Merchant-Id': merchant.id,
          'Idempotency-Key': crypto.randomUUID()
        },
        body: JSON.stringify({
          amount_paise: amountPaise, // <-- THE FINAL FIX IS HERE
          bank_account_id: bankAccount
        })
      })

      const data = await res.json()

      if (!res.ok) {
        setError(data.error || 'Failed to request payout')
      } else {
        setAmount('')
        setBankAccount('')
        fetchData()
      }
    } catch (err) {
      setError('Network error')
    } finally {
      setLoading(false)
    }
  }

  if (!merchant) return <div className="p-8 text-center">Loading or no merchants seeded...</div>

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8 font-sans text-gray-900">
      <div className="max-w-7xl mx-auto space-y-8">

        {/* Header */}
        <header className="flex justify-between items-center pb-6 border-b border-gray-200">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Playto Pay Dashboard</h1>
            <p className="text-sm text-gray-500">Real-time ledger & payout management</p>
          </div>

          <div className="flex items-center gap-4 bg-white p-2 rounded-lg border border-gray-200 shadow-sm">
            <label className="text-xs font-semibold text-gray-400 uppercase">Merchant</label>
            <select
              className="rounded border-gray-300 text-sm focus:ring-blue-500 focus:border-blue-500 p-1 bg-transparent font-medium"
              value={merchant.id}
              onChange={(e) => {
                const selected = allMerchants.find(m => m.id === e.target.value)
                setMerchant(selected)
              }}
            >
              {allMerchants.map(m => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
          </div>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Balance Cards */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 flex flex-col">
            <span className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Available Balance</span>
            <span className="text-4xl font-bold text-gray-900">₹{(merchant.balance / 100).toFixed(2)}</span>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 flex flex-col">
            <span className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Held Balance (Processing)</span>
            <span className="text-4xl font-bold text-orange-500">₹{(merchant.held_balance / 100).toFixed(2)}</span>
          </div>

          {/* Request Payout Form */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 row-span-2">
            <h2 className="text-lg font-semibold mb-4">Request Payout</h2>
            <form onSubmit={handlePayout} className="space-y-4">
              {error && <div className="p-3 bg-red-50 text-red-600 text-sm rounded-lg">{error}</div>}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Amount (INR)</label>
                <input
                  type="number"
                  step="0.01"
                  min="1"
                  max={merchant.balance / 100}
                  required
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 border p-2"
                  placeholder="0.00"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Bank Account ID</label>
                <input
                  type="text"
                  required
                  value={bankAccount}
                  onChange={(e) => setBankAccount(e.target.value)}
                  className="w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 border p-2"
                  placeholder="bank_xxxx"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full flex justify-center py-2 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 transition-colors"
              >
                {loading ? 'Processing...' : 'Withdraw Funds'}
              </button>
            </form>
          </div>

          {/* Payouts Table */}
          <div className="md:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 bg-gray-50/50">
              <h2 className="text-lg font-semibold">Payout History</h2>
            </div>
            <div className="overflow-x-auto max-h-[300px] overflow-y-auto">
              <table className="w-full text-left text-sm whitespace-nowrap">
                <thead className="bg-gray-50 text-gray-500 sticky top-0">
                  <tr>
                    <th className="px-6 py-3 font-medium">ID</th>
                    <th className="px-6 py-3 font-medium">Date</th>
                    <th className="px-6 py-3 font-medium">Bank Acc</th>
                    <th className="px-6 py-3 font-medium">Amount</th>
                    <th className="px-6 py-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {payouts.length === 0 ? (
                    <tr><td colSpan="5" className="px-6 py-8 text-center text-gray-500">No payouts yet.</td></tr>
                  ) : payouts.map(p => (
                    <tr key={p.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-6 py-4 text-gray-500 font-mono text-xs">{p.id.split('-')[0]}...</td>
                      <td className="px-6 py-4">{new Date(p.created_at).toLocaleString()}</td>
                      <td className="px-6 py-4 font-mono text-xs">{p.bank_account_id}</td>
                      {/* THE FIX IS ON THE NEXT LINE */}
                      <td className="px-6 py-4 font-medium">₹{(p.amount_paise / 100).toFixed(2)}</td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${p.status === 'COMPLETED' ? 'bg-green-50 text-green-700 border-green-200' :
                          p.status === 'FAILED' ? 'bg-red-50 text-red-700 border-red-200' :
                            p.status === 'PROCESSING' ? 'bg-orange-50 text-orange-700 border-orange-200 animate-pulse' :
                              'bg-yellow-50 text-yellow-700 border-yellow-200'
                          }`}>
                          {p.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Ledger/Transactions Table */}
          <div className="md:col-span-3 bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 bg-gray-50/50">
              <h2 className="text-lg font-semibold">Recent Ledger Entries</h2>
            </div>
            <div className="overflow-x-auto max-h-[300px] overflow-y-auto">
              <table className="w-full text-left text-sm whitespace-nowrap">
                <thead className="bg-gray-50 text-gray-500 sticky top-0">
                  <tr>
                    <th className="px-6 py-3 font-medium">Date</th>
                    <th className="px-6 py-3 font-medium">Description</th>
                    <th className="px-6 py-3 font-medium text-right">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {transactions.map(t => (
                    <tr key={t.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-6 py-4 text-gray-500">{new Date(t.created_at).toLocaleString()}</td>
                      <td className="px-6 py-4 text-gray-700">{t.description || 'System entry'}</td>
                      <td className={`px-6 py-4 text-right font-medium ${t.type === 'CREDIT' ? 'text-green-600' : 'text-gray-900'}`}>
                        {t.type === 'CREDIT' ? '+' : '-'} ₹{(t.amount / 100).toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}

export default App