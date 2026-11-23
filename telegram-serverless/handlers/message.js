import { api, fetch } from 'sdk';

const OWNER_ID = 5229720107;
const HELP = '🤖 Neteru Career Hunter працює!\n\n/start — перевірити бота\n/status — статус\n/search — знайти вакансії ServiceNow';

export default async function handleMessage(message) {
  // Only respond to the authorized owner in a private chat.
  if (Number(message?.from?.id) !== OWNER_ID || message?.chat?.type !== 'private') return;
  const chatId = message.chat.id;
  const cmd = (message.text || '').trim().split(/\s+/)[0].split('@')[0].toLowerCase();

  if (cmd === '/start' || cmd === '/help') {
    await api.sendMessage({ chat_id: chatId, text: HELP });
    return;
  }
  if (cmd === '/status') {
    await api.sendMessage({ chat_id: chatId, text: '✅ Telegram Serverless активний. Бот відповідає без GitHub Actions.\nПошук: Remotive. Ціль зарплати: €8 000 net/міс. (не перевірена).' });
    return;
  }
  if (cmd !== '/search') {
    await api.sendMessage({ chat_id: chatId, text: 'Напиши /start, /status або /search.' });
    return;
  }

  await api.sendMessage({ chat_id: chatId, text: '🔎 Перевіряю віддалені вакансії ServiceNow на Remotive…' });
  try {
    const response = await fetch('https://remotive.com/api/remote-jobs?search=servicenow&limit=100');
    if (!response.ok) throw new Error('Remotive HTTP ' + response.status);
    const data = await response.json();
    const jobs = (Array.isArray(data.jobs) ? data.jobs : []).filter((job) => {
      const title = String(job.title || '').toLowerCase();
      const location = String(job.candidate_required_location || '').toLowerCase();
      const description = String(job.description || '').toLowerCase();
      const combined = title + ' ' + location + ' ' + description;
      return (title.includes('servicenow') || title.includes('service now')) &&
        /(developer|architect|lead|engineer|consultant)/.test(title) &&
        /(remote|anywhere|worldwide|distributed)/.test(combined) &&
        !/(us only|usa only|united states only|must reside in the us|canada only|uk only|eu only|us-based only)/.test(combined);
    }).slice(0, 5);

    if (!jobs.length) {
      await api.sendMessage({ chat_id: chatId, text: 'Поки немає відповідних вакансій у Remotive. Це лише одне джерело; перевіримо інші пізніше.' });
      return;
    }
    for (const job of jobs) {
      const url = String(job.url || '');
      const text = [
        '💼 ' + String(job.title || 'ServiceNow role'),
        '🏢 ' + String(job.company_name || 'Компанія не вказана'),
        '🌍 ' + String(job.candidate_required_location || 'Локація не вказана'),
        '💶 ' + String(job.salary || 'Зарплата не вказана'),
        '⚠️ Робота з України та €8 000 net/міс. не підтверджені.',
      ].join('\n').slice(0, 3500);
      const payload = { chat_id: chatId, text };
      if (/^https:\/\//i.test(url)) {
        payload.reply_markup = { inline_keyboard: [[{ text: 'Відкрити вакансію', url }]] };
      }
      await api.sendMessage(payload);
    }
  } catch (error) {
    console.error('Remotive search failed:', String(error));
    await api.sendMessage({ chat_id: chatId, text: 'Не вдалося отримати вакансії з Remotive. Команди /start та /status продовжують працювати.' });
  }
}
