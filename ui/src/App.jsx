import { useCallback, useEffect, useState } from 'react'

const API_BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '')
const PAGES = { overview: 'Tổng quan', pending: 'Chờ phê duyệt', policies: 'Chính sách', audit: 'Nhật ký', administrators: 'Quản trị viên' }
const PAGE_SIZE = 50

function decodeBase64Url(value) {
  const padded = value.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - value.length % 4) % 4)
  return Uint8Array.from(atob(padded), (character) => character.charCodeAt(0))
}

function encodeBase64Url(value) {
  let binary = ''
  for (const byte of new Uint8Array(value)) binary += String.fromCharCode(byte)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

async function signApproval(privateKeyPem, approvalPayload) {
  const body = privateKeyPem.replace(/-----BEGIN PRIVATE KEY-----|-----END PRIVATE KEY-----|\s/g, '')
  const bytes = Uint8Array.from(atob(body), (character) => character.charCodeAt(0))
  const key = await crypto.subtle.importKey('pkcs8', bytes, { name: 'Ed25519' }, false, ['sign'])
  return encodeBase64Url(await crypto.subtle.sign('Ed25519', key, decodeBase64Url(approvalPayload)))
}

function endpointTitle(endpoint) {
  return endpoint === '/policy/update' ? 'Cập nhật chính sách' : endpoint === '/limits' ? 'Thay đổi hạn mức API' : endpoint
}

function timestamp(value) {
  if (value == null) return '—'
  const date = new Date(typeof value === 'number' ? value * 1000 : value)
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('vi-VN')
}

function ResourceError({ resource }) {
  return resource?.error ? <p className="resource-error" role="alert">{resource.error}</p> : null
}

export default function App() {
  const [page, setPage] = useState('overview')
  const [token, setToken] = useState(() => localStorage.getItem('quorum.adminToken') ?? '')
  const [privateKey, setPrivateKey] = useState(() => localStorage.getItem('quorum.privateKey') ?? '')
  const [tokenDraft, setTokenDraft] = useState(token)
  const [keyDraft, setKeyDraft] = useState(privateKey)
  const [resources, setResources] = useState({})
  const [selectedId, setSelectedId] = useState(null)
  const [toast, setToast] = useState(null)
  const [busy, setBusy] = useState(false)
  const [credentialsOpen, setCredentialsOpen] = useState(!token)
  const [policyDraft, setPolicyDraft] = useState(null)
  const [auditOffset, setAuditOffset] = useState(0)
  const [refreshId, setRefreshId] = useState(0)

  const request = useCallback(async (path, options = {}) => {
    const { queued = false, ...fetchOptions } = options
    const response = await fetch(`${API_BASE}${path}`, {
      ...fetchOptions,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}`, ...fetchOptions.headers },
    })
    const body = await response.json().catch(() => null)
    if (queued && response.status === 429 && body?.request_id) return body
    if (!response.ok) {
      if (response.status === 401) throw new Error('JWT không hợp lệ hoặc đã hết hạn. Mở Thông tin đăng nhập để cập nhật token.')
      const detail = body?.detail ?? body?.error
      throw new Error(response.status === 403
        ? `Không được phép: ${typeof detail === 'string' ? detail : 'kiểm tra quyền quản trị viên và tính toàn vẹn chính sách.'}`
        : typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : `Yêu cầu thất bại (${response.status}). Kiểm tra kết nối API.`)
    }
    if (body === null) throw new Error('API không trả về JSON. Kiểm tra cấu hình đường dẫn API/proxy.')
    return body
  }, [token])

  useEffect(() => {
    const controller = new AbortController()
    let running = false
    const paths = { overview: '/overview', pending: '/quorum/pending' }
    if (page === 'policies') paths.policies = '/policies'
    if (page === 'audit') paths.audit = `/audit?limit=${PAGE_SIZE}&offset=${auditOffset}`
    if (page === 'administrators') paths.administrators = '/administrators'
    async function load() {
      if (!token || running) return
      running = true
      await Promise.all(Object.entries(paths).map(async ([key, path]) => {
        try {
          const data = await request(path, { signal: controller.signal })
          if (!controller.signal.aborted) setResources((current) => ({ ...current, [key]: { data } }))
        } catch (error) {
          if (!controller.signal.aborted) setResources((current) => ({ ...current, [key]: { error: error.message } }))
        }
      }))
      running = false
    }
    load()
    const timer = setInterval(load, 5000)
    return () => { controller.abort(); clearInterval(timer) }
  }, [request, token, page, auditOffset, refreshId])

  const overview = resources.overview?.data
  const currentLimit = overview?.limit === null ? 'Chưa thiết lập' : overview?.limit ?? '—'
  const pending = resources.pending?.data ?? []
  const policies = resources.policies?.data
  const audit = resources.audit?.data
  const administrators = resources.administrators?.data
  const selected = pending.find((item) => item.id === selectedId) ?? pending[0]
  const integrityText = overview?.policy_integrity === true ? 'Đã xác minh' : overview?.policy_integrity === false ? 'Không toàn vẹn' : 'Chưa xác định'
  const refresh = () => setRefreshId((current) => current + 1)

  function navigate(nextPage) {
    if (nextPage === page) { refresh(); return }
    setPage(nextPage)
    setResources((current) => ({ overview: current.overview, pending: current.pending }))
  }

  function saveCredentials() {
    localStorage.setItem('quorum.adminToken', tokenDraft)
    localStorage.setItem('quorum.privateKey', keyDraft)
    setToken(tokenDraft)
    setPrivateKey(keyDraft)
    setResources({})
    setPolicyDraft(null)
    setAuditOffset(0)
    setCredentialsOpen(false)
    setToast({ kind: 'success', text: tokenDraft ? 'Đã lưu thông tin quản trị viên trong trình duyệt.' : 'Đã xóa thông tin đăng nhập đang dùng.' })
    refresh()
  }

  async function approve() {
    if (!selected) return
    setBusy(true)
    try {
      const signature = await signApproval(privateKey, selected.approval_payload)
      await request('/quorum/approve', { method: 'POST', body: JSON.stringify({ request_id: selected.id, signature }) })
      setToast({ kind: 'success', text: `Đã phê duyệt yêu cầu #${selected.id.slice(0, 8)}.` })
      refresh()
    } catch (error) {
      setToast({ kind: 'error', text: error.message })
    } finally { setBusy(false) }
  }

  async function submitPolicy(event) {
    event.preventDefault()
    setBusy(true)
    try {
      const policy = JSON.parse(policyDraft ?? JSON.stringify(policies.current))
      if (!policy || Array.isArray(policy) || typeof policy !== 'object') throw new Error('Chính sách phải là một JSON object.')
      const result = await request('/policy/update', { method: 'POST', queued: true, body: JSON.stringify({ policy }) })
      setToast({ kind: 'success', text: result.request_id ? `Đã đưa yêu cầu #${result.request_id} vào hàng đợi. Cần quản trị viên khác phê duyệt.` : 'API đã chấp nhận cập nhật chính sách.' })
      setPolicyDraft(null)
      navigate('pending')
      refresh()
    } catch (error) {
      setToast({ kind: 'error', text: error instanceof SyntaxError ? 'JSON không hợp lệ. Kiểm tra cú pháp trước khi gửi.' : error.message })
    } finally { setBusy(false) }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">◇</span><div><strong>QUORUM</strong><small>TideCloak · API Guard</small></div></div>
        <nav aria-label="Điều hướng chính">{Object.entries(PAGES).map(([key, label]) => <button key={key} className={page === key ? 'active' : ''} aria-current={page === key ? 'page' : undefined} onClick={() => navigate(key)}>{label}{key === 'pending' && resources.pending?.data && <b>{pending.length}</b>}</button>)}</nav>
        <div className="sidebar-foot">Hackathon demo · Khóa ký cục bộ</div>
      </aside>
      <div className="workspace">
        <div className="topbar"><div>Bảo mật <i>/</i> <strong>{PAGES[page]}</strong> <em>Demo</em></div><button onClick={() => setCredentialsOpen(true)}>Thông tin đăng nhập</button></div>
        <main>
          {toast && <div className={`toast ${toast.kind}`} role="status">{toast.text}<button aria-label="Đóng thông báo" onClick={() => setToast(null)}>×</button></div>}
          <header className="page-header"><div><h1>{PAGES[page]}</h1><p>Hành động nhạy cảm cần chữ ký của 2 quản trị viên.</p></div><button className="outline" onClick={refresh}>Làm mới</button></header>
          {!token ? <section className="panel content-panel"><h2>Cần đăng nhập quản trị viên</h2><p>Nhập JWT để tải dữ liệu thực từ API. Khóa riêng chỉ cần khi ký phê duyệt.</p><button className="outline" onClick={() => setCredentialsOpen(true)}>Thiết lập thông tin</button></section> : <>
            {(page === 'overview' || page === 'pending') && <>
              <ResourceError resource={resources.overview}/>
              {!resources.overview && <p role="status">Đang tải tổng quan…</p>}
              <div className="stats">
                <section><div><small>Chờ phê duyệt</small><strong>{overview?.pending_count ?? '—'}</strong></div></section>
                <section><div><small>Đã phê duyệt</small><strong>{overview?.approved_count ?? '—'}</strong></div></section>
                <section><div><small>Hạn mức hiện tại</small><strong>{currentLimit}</strong></div></section>
              </div>
            </>}
            {page === 'overview' && <section className="panel content-panel"><h2>Trạng thái chính sách</h2><dl className="record"><dt>Phiên bản</dt><dd>{overview?.policy_version ?? '—'}</dd><dt>Tính toàn vẹn</dt><dd className={overview?.policy_integrity === false ? 'error-text' : ''}>{integrityText}</dd><dt>Merkle root đã lưu</dt><dd><code>{overview?.policy_root ?? '—'}</code></dd></dl><button className="outline" onClick={() => navigate('pending')}>Mở hàng đợi phê duyệt</button></section>}
            {page === 'pending' && <>
              <ResourceError resource={resources.pending}/>
              {!resources.pending && <p role="status">Đang tải hàng đợi…</p>}
              <div className="dashboard-grid">
                <section className="panel queue-panel"><div className="panel-title"><h2>Yêu cầu đang chờ</h2></div><div className="queue">
                  {resources.pending?.data && pending.length === 0 && <div className="empty"><strong>Không có yêu cầu đang chờ</strong><small>Gửi cập nhật trong trang Chính sách để bắt đầu.</small></div>}
                  {pending.map((item) => <button key={item.id} className={item.id === selected?.id ? 'queue-item selected' : 'queue-item'} onClick={() => setSelectedId(item.id)}><span className="item-main"><strong>{endpointTitle(item.endpoint)}</strong><code>POST {item.endpoint}</code><small>{item.admin} · {timestamp(item.timestamp)}</small></span><span className="badge">Chờ phê duyệt</span></button>)}
                </div></section>
                <section className="panel detail-panel">{selected ? <>
                  <div className="detail-head"><div><h2>{endpointTitle(selected.endpoint)}</h2><code>#{selected.id}</code></div></div>
                  {selected.endpoint === '/limits' && <div className="limit-flow"><div><small>Hạn mức hiện tại</small><strong>{currentLimit}</strong></div><b>→</b><div><small>Đề xuất</small><strong>{selected.payload?.value ?? '—'}</strong></div></div>}
                  <pre className="payload">{JSON.stringify(selected.payload, null, 2)}</pre>
                  <dl className="record"><dt>Người yêu cầu</dt><dd>{selected.admin}</dd><dt>Endpoint</dt><dd>{selected.endpoint}</dd><dt>Thời gian</dt><dd>{timestamp(selected.timestamp)}</dd></dl>
                  <div className="locked">Cần chữ ký của quản trị viên khác — hành động chưa được thực thi.</div>
                  <button className="approve" disabled={busy || !privateKey} onClick={approve}>{busy ? 'Đang ký…' : 'Ký & phê duyệt'}</button>
                  {!privateKey && <button className="credential-link" onClick={() => setCredentialsOpen(true)}>Thiết lập khóa ký để phê duyệt</button>}
                </> : <div className="detail-empty"><h2>Chưa chọn yêu cầu</h2><p>Chi tiết yêu cầu sẽ hiển thị tại đây.</p></div>}</section>
              </div>
            </>}
            {page === 'policies' && <>
              <ResourceError resource={resources.policies}/>
              {!resources.policies && <p role="status">Đang tải chính sách…</p>}
              {policies && <div className="view-stack"><section className="panel content-panel"><h2>Chính sách hiện tại</h2><pre className="payload">{JSON.stringify(policies.current, null, 2)}</pre></section>
                <section className="panel content-panel"><h2>Đề xuất cập nhật</h2><p>Thay đổi chỉ được áp dụng sau khi quản trị viên khác ký phê duyệt.</p><form onSubmit={submitPolicy}><label htmlFor="policy-json">Nội dung JSON</label><textarea id="policy-json" className="json-editor" rows="14" spellCheck={false} value={policyDraft ?? JSON.stringify(policies.current, null, 2)} onChange={(event) => setPolicyDraft(event.target.value)}/><div className="form-actions"><button type="button" className="outline" onClick={() => setPolicyDraft(null)}>Khôi phục bản hiện tại</button><button className="approve" disabled={busy}>{busy ? 'Đang gửi…' : 'Gửi yêu cầu phê duyệt'}</button></div></form></section>
                <section className="panel content-panel"><h2>Lịch sử phiên bản</h2><div className="table-scroll"><table><thead><tr><th>Phiên bản</th><th>Merkle root</th><th>Thời gian</th></tr></thead><tbody>{policies.versions.map((version) => <tr key={version.version}><td>{version.version}</td><td className="hash-cell"><code>{version.root}</code></td><td>{timestamp(version.created_at)}</td></tr>)}</tbody></table></div>{policies.versions.length === 0 && <p>Chưa có phiên bản được lưu.</p>}</section></div>}
            </>}
            {page === 'audit' && <>
              <ResourceError resource={resources.audit}/>
              {!resources.audit && <p role="status">Đang tải nhật ký…</p>}
              {audit && <section className="panel content-panel"><h2>Nhật ký hoạt động ({audit.total})</h2><div className="table-scroll"><table><thead><tr><th>Thời gian</th><th>Sự kiện</th><th>Quản trị viên</th><th>Yêu cầu / Endpoint</th><th>Chi tiết</th></tr></thead><tbody>{audit.items.map((item) => <tr key={item.id}><td>{timestamp(item.timestamp)}</td><td>{item.event}</td><td>{item.actor ?? '—'}</td><td><code>{item.request_id ?? '—'}</code><br/>{item.endpoint ?? '—'}</td><td><pre>{typeof item.detail === 'string' ? item.detail : JSON.stringify(item.detail, null, 2)}</pre></td></tr>)}</tbody></table></div>{audit.items.length === 0 && <p>Không có sự kiện trên trang này.</p>}<div className="pagination"><button className="outline" disabled={auditOffset === 0} onClick={() => { setResources((current) => ({ ...current, audit: undefined })); setAuditOffset(Math.max(0, auditOffset - PAGE_SIZE)) }}>Trang trước</button><span>Trang {Math.floor(auditOffset / PAGE_SIZE) + 1}</span><button className="outline" disabled={auditOffset + PAGE_SIZE >= audit.total} onClick={() => { setResources((current) => ({ ...current, audit: undefined })); setAuditOffset(auditOffset + PAGE_SIZE) }}>Trang sau</button></div></section>}
            </>}
            {page === 'administrators' && <>
              <ResourceError resource={resources.administrators}/>
              {!resources.administrators && <p role="status">Đang tải quản trị viên…</p>}
              {administrators && <section className="panel content-panel"><h2>Quản trị viên đã cấu hình</h2><p>Quorum yêu cầu {administrators.quorum} quản trị viên.</p><div className="table-scroll"><table><thead><tr><th>Định danh</th><th>Fingerprint khóa công khai</th><th>Trạng thái khóa</th></tr></thead><tbody>{administrators.items.map((admin) => <tr key={admin.id}><td>{admin.id}</td><td className="hash-cell"><code>{admin.public_key_fingerprint ?? '—'}</code></td><td>{admin.key_available ? 'Có khóa công khai' : 'Khóa không khả dụng'}</td></tr>)}</tbody></table></div>{administrators.items.length === 0 && <p>Chưa cấu hình quản trị viên.</p>}</section>}
            </>}
          </>}
        </main>
      </div>
      {credentialsOpen && <div className="modal-backdrop" onMouseDown={() => setCredentialsOpen(false)}><section className="credential-modal" role="dialog" aria-modal="true" aria-labelledby="credentials-title" onMouseDown={(event) => event.stopPropagation()}><button className="close" aria-label="Đóng thiết lập" onClick={() => setCredentialsOpen(false)}>×</button><p className="kicker">THÔNG TIN KÝ CỤC BỘ</p><h2 id="credentials-title">Thiết lập quản trị viên</h2><p>Chỉ dùng khóa demo. JWT và khóa riêng được lưu trong localStorage của trình duyệt này; không dùng khóa sản xuất. Khóa riêng không được gửi tới API.</p><label>Administrator JWT<textarea rows="4" value={tokenDraft} onChange={(event) => setTokenDraft(event.target.value.trim())}/></label><label>Ed25519 PKCS8 private key<textarea rows="6" value={keyDraft} onChange={(event) => setKeyDraft(event.target.value)}/></label><button className="approve" onClick={saveCredentials}>Lưu thông tin</button></section></div>}
    </div>
  )
}
