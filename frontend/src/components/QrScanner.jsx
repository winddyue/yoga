import { useEffect, useRef, useState } from 'react';
import { Html5Qrcode } from 'html5-qrcode';

// 二维码扫描：解析二维码内容（JSON 字符串）后回填评估表单
export default function QrScanner({ onScan, onClose }) {
  const ref = useRef(null);
  const [err, setErr] = useState('');
  useEffect(() => {
    const qr = new Html5Qrcode('qr-reader');
    qr.start(
      { facingMode: 'environment' },
      { fps: 10, qrbox: 220 },
      (text) => {
        try {
          const data = JSON.parse(text); // 约定二维码内容为评估字段 JSON
          onScan(data);
        } catch {
          setErr('二维码内容不是有效的评估数据');
        }
      },
      () => {}
    ).catch(() => setErr('无法打开摄像头，请检查权限'));
    return () => { qr.stop().catch(() => {}); };
  }, []);
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="card w-full max-w-sm">
        <div className="font-medium mb-2">扫描评估二维码</div>
        <div id="qr-reader" ref={ref} />
        {err && <div className="text-red-500 text-sm mt-2">{err}</div>}
        <button className="btn-ghost mt-3 w-full" onClick={onClose}>关闭</button>
      </div>
    </div>
  );
}
