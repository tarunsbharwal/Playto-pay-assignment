import { useState, useEffect, useCallback } from 'react'

const API_BASE = "https://playto-pay-assignment-1.onrender.com/api/v1";

function App() {
  const [allMerchants, setAllMerchants] = useState([])
  const [activeMerchantId, setActiveMerchantId] = useState(null)
  const [merchant, setMerchant] = useState(null)
  const [transactions, setTransactions] = useState([])
  const [payouts, setPayouts] = useState([])

  const [amount, setAmount] = useState('')
  const [bankAccount, setBankAccount] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // 1. Initial Load: Get the list of merchants only once
  useEffect(() => {
    const init = async () => {
      try {
        const res = await fetch(`${API_BASE}/merchants/`)
        const data = await res.json()
        const merchantsList = data.results ? data.results : data
        setAllMerchants(merchantsList)

        // Default to the first merchant if none selected
        if (merchantsList.length > 0 && !activeMerchantId) {
          setActiveMerchantId(merchantsList[0].id)
        }
      } catch (err) {
        console.error("Initial fetch failed:", err)
      }
    }
    init()
  }, [])

  // 2. Data Polling: Fetch details only for the currently active merchant
  const refreshData = useCallback(async () => {
    if (!activeMerchantId) return

    try {
      // Sync merchant balance
      const mRes = await fetch(`${API_BASE}/merchants/`)
      const mData = await mRes.json()
      const list = mData.results ? mData.results : mData
      const current = list.find(m => m.id === activeMerchantId)
      if (current) setMerchant(current)

      // Get transactions
      const tRes = await fetch(`${API_BASE}/merchants/${activeMerchantId}/transactions/`)
      const tData = await tRes.json()
      setTransactions(tData.results ? tData.results : tData)

      // Get payouts
      const pRes = await fetch(`${API_BASE}/merchants/${activeMerchantId}/payouts/`)
      const pData = await pRes.json()
      setPayouts(pData.results ? pData.results : pData)
    } catch (err) {
      console.error("Polling error:", err)
    }
  }, [activeMerchantId])

  useEffect(() => {
    refreshData()
    const interval = setInterval(refreshData, 3000) // Poll every 3 seconds for stability
    return () => clearInterval(interval)
  }, [refreshData])

  const handlePayout = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const amountPaise = Math.round(parseFloat(amount) * 100)
      const res = await fetch(`${API_BASE}/payouts/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Merchant-Id': activeMerchantId,
          'Idempotency-Key': crypto.randomUUID()
        },
        body: JSON.stringify({
          amount_paise: amountPaise,
          bank_account_id: bankAccount
        })
      })

      if (!res.ok) {
        const data = await res.json()
        setError(data.error || 'Failed to request payout')
      } else {
        setAmount('')
        setBankAccount('')
        refreshData()
      }
    } catch (err) {
      setError('Network error')
    } finally {
      setLoading(false)
    }
  }

  if (!merchant) return <div className="p-8 text-center font-sans">Connecting to live ledger...</div>

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 font-sans text-gray-900">
      <div className="max-w-7xl mx-auto space-y-8">

        {/* Header */}
        <header className="flex justify-between items-center pb-6 border-b border-gray-200">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Playto Pay Cloud</h1>
            <p className="text-sm text-gray-500">Live Payout Engine</p>
          </div>

          <div className="flex items-center gap-4 bg-white p-2 rounded-lg border border-gray-200 shadow-sm">
            <label className="text-xs font-semibold text-gray-400 uppercase">Merchant</label>
            <select
              className="rounded border-gray-300 text-sm p-1 bg-transparent font-medium cursor-pointer"
              value={activeMerchantId}
              onChange={(e) => setActiveMerchantId(e.target.value)}
            >
              {allMerchants.map(m => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
          </div>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Balance Cards */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <span className="text-sm font-medium text-gray-500 uppercase">Available Balance</span>
            <div className="text-4xl font-bold mt-2">
              ₹{(merchant.balance / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <span className="text-sm font-medium text-gray-500 uppercase">Processing (Held)</span>
            <div className="text-4xl font-bold mt-2 text-orange-500">
              ₹{(merchant.held_balance / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>
          </div>

          {/* Form */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 row-span-2">
            <h2 className="text-lg font-semibold mb-4">Request Payout</h2>
            <form onSubmit={handlePayout} className="space-y-4">
              {error && <div className="p-3 bg-red-50 text-red-600 text-sm rounded-lg border border-red-100">{error}</div>}
              <div>
                <label className="block text-sm font-medium text-gray-700">Amount (INR)</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="w-full rounded-lg border-gray-300 border p-2 mt-1"
                  placeholder="0.00"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Bank Account ID</label>
                <input
                  type="text"
                  required
                  value={bankAccount}
                  onChange={(e) => setBankAccount(e.target.value)}
                  className="w-full rounded-lg border-gray-300 border p-2 mt-1"
                  placeholder="bank_123"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 rounded-lg text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 font-medium"
              >
                {loading ? 'Processing...' : 'Withdraw Funds'}
              </button>
            </form>
          </div>

          {/* History */}
          <div className="md:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 bg-gray-50/50 font-semibold">Payout History</div>
            <div className="overflow-x-auto max-h-[300px]">
              <table className="w-full text-left text-sm">
                <thead className="bg-gray-50 text-gray-500 sticky top-0">
                  <tr>
                    <th className="px-6 py-3">Reference</th>
                    <th className="px-6 py-3">Amount</th>
                    <th className="px-6 py-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {payouts.map(p => (
                    <tr key={p.id} className="hover:bg-gray-50/50">
                      <td className="px-6 py-4 font-mono text-xs">{p.id.split('-')[0]}...</td>
                      <td className="px-6 py-4 font-medium">₹{(p.amount_paise / 100).toFixed(2)}</td>
                      <td className="px-6 py-4">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${p.status === 'COMPLETED' ? 'bg-green-50 text-green-700 border-green-200' :
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

          {/* Ledger */}
          <div className="md:col-span-3 bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 bg-gray-50/50 font-semibold">Ledger Entries</div>
            <div className="overflow-x-auto max-h-[300px]">
              <table className="w-full text-left text-sm">
                <thead className="bg-gray-50 text-gray-500 sticky top-0">
                  <tr>
                    <th className="px-6 py-3">Date</th>
                    <th className="px-6 py-3">Description</th>
                    <th className="px-6 py-3 text-right">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {transactions.map(t => (
                    <tr key={t.id} className="hover:bg-gray-50/50">
                      <td className="px-6 py-4 text-gray-500">{new Date(t.created_at).toLocaleString()}</td>
                      <td className="px-6 py-4">{t.description}</td>
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