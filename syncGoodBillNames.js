// ============================================================
// Google Apps Script: Sync GoodBillName to Supabase
// ดึงข้อมูล GoodBillName จาก Google Sheets เข้าสู่ Supabase ผ่าน API
// ============================================================
function syncGoodBillNameToSupabase() {
  const SPREADSHEET_ID = "1Z48qT3LXYozhlh_ZBHzn9e4x1kfX_bOLHQtaksj-ZXU";
  const SHEET_NAME = "Main Product";
  const API_URL = "https://quotation-api-h4ta.onrender.com/api/sync/good-bill-names";

  let ss;
  try {
    ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  } catch (e) {
    // กรณีที่ Script อยู่ในไฟล์ชีตนี้อยู่แล้ว
    ss = SpreadsheetApp.getActiveSpreadsheet();
  }

  const sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    throw new Error("❌ ไม่พบชีตชื่อ '" + SHEET_NAME + "' ในไฟล์ Spreadsheet");
  }

  const lastRow = sheet.getLastRow();
  if (lastRow < 2) {
    Logger.log("⚠️ ไม่พบแถวข้อมูลในชีต '" + SHEET_NAME + "'");
    return;
  }

  Logger.log("📖 กำลังอ่านข้อมูลชีต '" + SHEET_NAME + "' ทั้งหมด " + (lastRow - 1) + " แถว...");
  // อ่านข้อมูลตั้งแต่แถว 2: Column A (GoodID) ถึง Column E (GoodBillName)
  const rangeValues = sheet.getRange(2, 1, lastRow - 1, 5).getValues();

  const payload = [];
  for (let i = 0; i < rangeValues.length; i++) {
    const rawGoodId = rangeValues[i][0];
    const rawBillName = rangeValues[i][4];

    if (rawGoodId != null && rawGoodId !== "" && rawBillName != null && rawBillName !== "") {
      const goodId = String(rawGoodId).trim();
      const billName = String(rawBillName).trim();
      if (goodId && billName && billName !== "0" && billName.toLowerCase() !== "goodbillname") {
        payload.push({
          good_id: goodId,
          good_bill_name: billName
        });
      }
    }
  }

  Logger.log("📦 คัดกรองได้ข้อมูลที่ถูกต้องทั้งหมด: " + payload.length + " รายการ");
  if (payload.length === 0) {
    Logger.log("⚠️ ไม่มีข้อมูลที่จะส่ง");
    return;
  }

  // ส่งข้อมูลเป็นชุดๆ ละ 5,000 แถว เพื่อความรวดเร็วและไม่ติดขีดจำกัดขนาด Payload
  const BATCH_SIZE = 5000;
  let totalUpdated = 0;
  const totalBatches = Math.ceil(payload.length / BATCH_SIZE);

  for (let b = 0; b < totalBatches; b++) {
    const startIdx = b * BATCH_SIZE;
    const chunk = payload.slice(startIdx, startIdx + BATCH_SIZE);

    Logger.log("🚀 กำลังส่งชุดที่ " + (b + 1) + "/" + totalBatches + " (" + chunk.length + " รายการ)...");

    const options = {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(chunk),
      muteHttpExceptions: true
    };

    const res = UrlFetchApp.fetch(API_URL, options);
    const code = res.getResponseCode();
    const text = res.getContentText();

    if (code >= 200 && code < 300) {
      try {
        const json = JSON.parse(text);
        totalUpdated += (json.updated || chunk.length);
        Logger.log("   ✅ สำเร็จ: อัปเดตแล้ว " + (json.updated || chunk.length) + " แถว");
      } catch (e) {
        totalUpdated += chunk.length;
      }
    } else {
      Logger.log("   ❌ ล้มเหลวในชุดที่ " + (b + 1) + " (HTTP " + code + "): " + text.substring(0, 200));
    }
  }

  Logger.log("🎉 เสร็จสิ้นสมบูรณ์! อัปเดต GoodBillName ลง Supabase แล้วรวม " + totalUpdated + " รายการ");
}
