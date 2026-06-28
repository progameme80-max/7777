import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import requests
import json
import io
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict
from flask import Flask
import threading
import os
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# --- FLASK WEB SUNUCUSU ---
app = Flask('')

@app.route('/')
def home():
    return "Bot 7/24 Aktif!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()

keep_alive()

# ==================== KONFIGÜRASYON ====================
TOKEN = os.getenv('TOKEN')
SAHI_IDSI = int(os.getenv('BOT_OWNER_ID', '0'))
API_BASE_URL = os.getenv('API_BASE_URL', 'https://arastir.vip/api')

if not TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable not set!")
if SAHI_IDSI == 0:
    raise ValueError("BOT_OWNER_ID environment variable not set!")

# ==================== KEY YÖNETİMİ ====================
class KeyManager:
    def __init__(self):
        self.keys: Dict[str, dict] = {}
        self.max_usage = 10
        self.key_duration_hours = 24
        self.user_keys: Dict[int, str] = {}
        
    def generate_key(self, user_id: int) -> str:
        key = secrets.token_hex(8)
        now = datetime.now()
        self.keys[key] = {
            "user_id": user_id,
            "created_at": now,
            "expires_at": now + timedelta(hours=self.key_duration_hours),
            "usage_count": 0,
            "max_usage": self.max_usage,
            "owner_id": user_id
        }
        self.user_keys[user_id] = key
        return key
    
    def validate_key(self, key: str, user_id: int) -> tuple:
        if key not in self.keys:
            return False, "❌ Geçersiz key!", 0
        
        data = self.keys[key]
        
        if data["user_id"] != user_id:
            return False, "❌ Bu key size ait değil!", 0
        
        if datetime.now() > data["expires_at"]:
            del self.keys[key]
            if user_id in self.user_keys:
                del self.user_keys[user_id]
            return False, "❌ Key'in süresi dolmuş!", 0
        
        if data["usage_count"] >= data["max_usage"]:
            return False, "❌ Key'in kullanım hakkı bitti!", 0
        
        kalan = data["max_usage"] - data["usage_count"]
        return True, f"✅ Key geçerli! Kalan {kalan} sorgu hakkı.", kalan
    
    def use_key(self, key: str, user_id: int) -> tuple:
        valid, msg, kalan = self.validate_key(key, user_id)
        if not valid:
            return False, msg, 0
        
        self.keys[key]["usage_count"] += 1
        kalan = self.keys[key]["max_usage"] - self.keys[key]["usage_count"]
        return True, f"✅ Sorgu başarılı! Kalan {kalan} hakkınız.", kalan
    
    def get_user_key(self, user_id: int) -> Optional[str]:
        return self.user_keys.get(user_id)
    
    def get_key_info(self, key: str) -> Optional[dict]:
        if key not in self.keys:
            return None
        
        data = self.keys[key]
        kalan = data["max_usage"] - data["usage_count"]
        expires_in = (data["expires_at"] - datetime.now()).total_seconds() / 3600
        
        return {
            "kalan_hak": kalan,
            "kullanım": data["usage_count"],
            "max_kullanım": data["max_usage"],
            "süre": f"{expires_in:.1f} saat",
            "oluşturma": data["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
            "sona_erme": data["expires_at"].strftime("%Y-%m-%d %H:%M:%S"),
            "sahibi": data["user_id"]
        }

key_manager = KeyManager()

# ==================== BOTU BAŞLAT ====================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# ==================== API SINIFI ====================
class NufusAPI:
    def __init__(self):
        self.base_url = API_BASE_URL
    
    def tc_sorgu(self, tc: str) -> dict:
        try:
            r = requests.get(f"{self.base_url}/tc.php", params={"tc": tc}, timeout=30)
            return {"success": r.status_code == 200, "data": r.json() if r.status_code == 200 else []}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}
    
    def adsoyad_sorgu(self, adi: str, soyadi: str = None, il: str = None, ilce: str = None) -> dict:
        params = {"adi": adi}
        if soyadi: params["soyadi"] = soyadi
        if il: params["il"] = il
        if ilce: params["ilce"] = ilce
        try:
            r = requests.get(f"{self.base_url}/adsoyad.php", params=params, timeout=30)
            return {"success": r.status_code == 200, "data": r.json() if r.status_code == 200 else []}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}
    
    def adres_sorgu(self, tc: str) -> dict:
        try:
            r = requests.get(f"{self.base_url}/adres.php", params={"tc": tc}, timeout=30)
            return {"success": r.status_code == 200, "data": r.json() if r.status_code == 200 else []}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}
    
    def gsmden_tc(self, gsm: str) -> dict:
        try:
            r = requests.get(f"{self.base_url}/gsmtc.php", params={"gsm": gsm}, timeout=30)
            return {"success": r.status_code == 200, "data": r.json() if r.status_code == 200 else []}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}
    
    def tcdengsm(self, tc: str) -> dict:
        try:
            r = requests.get(f"{self.base_url}/tcgsm.php", params={"tc": tc}, timeout=30)
            return {"success": r.status_code == 200, "data": r.json() if r.status_code == 200 else []}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}
    
    def isyeri_sorgu(self, tc: str) -> dict:
        try:
            r = requests.get(f"{self.base_url}/isyeri.php", params={"tc": tc}, timeout=30)
            return {"success": r.status_code == 200, "data": r.json() if r.status_code == 200 else []}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}
    
    def sulale_sorgu(self, tc: str) -> dict:
        try:
            r = requests.get(f"{self.base_url}/sulale.php", params={"tc": tc}, timeout=30)
            return {"success": r.status_code == 200, "data": r.json() if r.status_code == 200 else []}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}

api = NufusAPI()

# ==================== FORMATLAYICI ====================
def create_txt_content(data, baslik, sorgu_tipi, aranan):
    content = []
    content.append("=" * 60)
    content.append(f"  {baslik}")
    content.append("=" * 60)
    content.append(f"  Sorgu Tarihi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    content.append(f"  Sorgu Tipi: {sorgu_tipi}")
    content.append(f"  Aranan: {aranan}")
    content.append("=" * 60)
    content.append("")
    
    if isinstance(data, list):
        for idx, item in enumerate(data, 1):
            if isinstance(item, dict):
                content.append(f"--- KAYIT {idx} ---")
                for key, value in item.items():
                    content.append(f"  {key}: {value}")
                content.append("")
            else:
                content.append(f"{idx}. {item}")
    elif isinstance(data, dict):
        for key, value in data.items():
            content.append(f"  {key}: {value}")
    else:
        content.append(str(data))
    
    content.append("")
    content.append("=" * 60)
    content.append("  Sorgu Sonu")
    content.append("=" * 60)
    
    return "\n".join(content)

def format_tc(data):
    if not data.get("success"):
        return None, f"❌ Hata: {data.get('error', 'Bilinmeyen')}"
    result = data.get("data", [])
    if not result:
        return None, "❌ Sonuç bulunamadı!"
    if isinstance(result, list) and result:
        result = result[0]
    
    embed = discord.Embed(title="📋 TC Kimlik Bilgileri", color=discord.Color.blue())
    embed.add_field(name="TC", value=result.get('tc', 'Bilinmiyor'), inline=False)
    embed.add_field(name="Ad", value=result.get('adi', 'Bilinmiyor'), inline=True)
    embed.add_field(name="Soyad", value=result.get('soyadi', 'Bilinmiyor'), inline=True)
    embed.add_field(name="Baba", value=result.get('baba', 'Bilinmiyor'), inline=True)
    embed.add_field(name="Anne", value=result.get('anne', 'Bilinmiyor'), inline=True)
    embed.add_field(name="Doğum Yılı", value=result.get('dogumyili', 'Bilinmiyor'), inline=True)
    embed.add_field(name="Doğum Yeri", value=result.get('dogumyeri', 'Bilinmiyor'), inline=False)
    embed.add_field(name="İl/İlçe", value=f"{result.get('il', 'Bilinmiyor')}/{result.get('ilce', 'Bilinmiyor')}", inline=True)
    embed.add_field(name="Cinsiyet", value=result.get('cinsiyet', 'Bilinmiyor'), inline=True)
    embed.add_field(name="Medeni Hal", value=result.get('medenihal', 'Bilinmiyor'), inline=True)
    embed.set_footer(text="🔍 Nüfus Sorgu")
    return embed, None

def format_adres(data):
    if not data.get("success"):
        return None, f"❌ Hata: {data.get('error', 'Bilinmeyen')}"
    result = data.get("data", [])
    if not result:
        return None, "❌ Adres bulunamadı!"
    if isinstance(result, list) and result:
        result = result[0]
    
    embed = discord.Embed(title="📍 İkametgah Adresi", color=discord.Color.green())
    embed.add_field(name="TC", value=result.get('tc', 'Bilinmiyor'), inline=False)
    embed.add_field(name="Adres", value=result.get('adres', 'Bilinmiyor'), inline=False)
    embed.add_field(name="İl/İlçe", value=f"{result.get('il', 'Bilinmiyor')}/{result.get('ilce', 'Bilinmiyor')}", inline=True)
    embed.add_field(name="Mahalle", value=result.get('mahalle', 'Bilinmiyor'), inline=True)
    embed.add_field(name="Sokak", value=result.get('sokak', 'Bilinmiyor'), inline=True)
    embed.set_footer(text="🔍 Nüfus Sorgu")
    return embed, None

def format_sulale(data):
    if not data.get("success"):
        return None, f"❌ Hata: {data.get('error', 'Bilinmeyen')}"
    result = data.get("data", [])
    if not result:
        return None, "❌ Sülale bilgisi bulunamadı!"
    
    embed = discord.Embed(title="👨‍👩‍👧‍👦 Sülale Ağacı", color=discord.Color.purple())
    
    yakinliklar = {"Kendisi": [], "Anne": [], "Baba": [], "Kardes": [],
                  "Anneanne": [], "DedeAnne": [], "Babaanne": [],
                  "DedeBaba": [], "TeyzeDayi": [], "AmcaHala": []}
    
    for kisi in result:
        yakinlik = kisi.get('yakinlik', 'Bilinmiyor')
        if yakinlik in yakinliklar:
            isim = f"{kisi.get('adi', '?')} {kisi.get('soyadi', '?')}"
            yakinliklar[yakinlik].append(isim)
    
    for yakinlik, kisiler in yakinliklar.items():
        if kisiler:
            embed.add_field(name=yakinlik, value="\n".join(kisiler), inline=True)
    
    embed.set_footer(text="🔍 Nüfus Sorgu")
    return embed, None

def format_list(data, baslik):
    if not data.get("success"):
        return None, f"❌ Hata: {data.get('error', 'Bilinmeyen')}"
    result = data.get("data", [])
    if not result:
        return None, "❌ Sonuç bulunamadı!"
    
    embed = discord.Embed(title=f"📊 {baslik}", description=f"{len(result)} kayıt bulundu.", color=discord.Color.teal())
    embed.set_footer(text="Sonuçlar txt dosyasında")
    return embed, None

# ==================== YÖNETİCİ BİLDİRİMİ ====================
async def send_admin_notification(user, sorgu_tipi, aranan, result_data):
    try:
        owner = await bot.fetch_user(SAHI_IDSI)
        if not owner:
            return
        
        embed = discord.Embed(
            title="🔔 YENİ SORGU",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        embed.add_field(name="👤 Sorgu Yapan", value=f"{user.name}#{user.discriminator} (ID: {user.id})", inline=False)
        embed.add_field(name="📌 Sorgu Tipi", value=sorgu_tipi, inline=True)
        embed.add_field(name="🔍 Aranan", value=aranan, inline=True)
        
        if result_data and isinstance(result_data, list):
            embed.add_field(name="📊 Sonuç Sayısı", value=str(len(result_data)), inline=True)
            if len(result_data) > 0 and isinstance(result_data[0], dict):
                ilk = result_data[0]
                ozet = f"Ad: {ilk.get('adi', '?')} {ilk.get('soyadi', '?')}\nTC: {ilk.get('tc', '?')}"
                embed.add_field(name="📋 İlk Kayıt", value=ozet, inline=False)
        
        await owner.send(embed=embed)
    except Exception as e:
        print(f"Yönetici bildirimi hatası: {e}")

# ==================== VIEWS ====================
class MenuView(View):
    def __init__(self, key: str):
        super().__init__(timeout=None)
        self.key = key
        self.add_item(Button(label="🔍 TC Sorgu", custom_id="tc", style=discord.ButtonStyle.danger))
        self.add_item(Button(label="📝 Ad Soyad", custom_id="adsoyad", style=discord.ButtonStyle.primary))
        self.add_item(Button(label="📍 Adres", custom_id="adres", style=discord.ButtonStyle.success))
        self.add_item(Button(label="📱 GSM'den TC", custom_id="gsmden", style=discord.ButtonStyle.secondary))
        self.add_item(Button(label="📱 TC'den GSM", custom_id="tcdengsm", style=discord.ButtonStyle.secondary))
        self.add_item(Button(label="🏢 İşyeri/SGK", custom_id="isyeri", style=discord.ButtonStyle.primary))
        self.add_item(Button(label="👨‍👩‍👧‍👦 Sülale", custom_id="sulale", style=discord.ButtonStyle.danger))

class SorguModal(Modal):
    def __init__(self, title: str, sorgu_tipi: str, fields: list, key: str, sorgu_adi: str):
        super().__init__(title=title)
        self.sorgu_tipi = sorgu_tipi
        self.key = key
        self.sorgu_adi = sorgu_adi
        for field in fields:
            item = TextInput(
                label=field["label"],
                placeholder=field.get("placeholder", ""),
                required=field.get("required", True),
                min_length=field.get("min_length", 1),
                max_length=field.get("max_length", 100)
            )
            self.add_item(item)
    
    async def on_submit(self, interaction: discord.Interaction):
        valid, msg, kalan = key_manager.validate_key(self.key, interaction.user.id)
        if not valid:
            await interaction.response.send_message(msg, ephemeral=True)
            return
        
        await interaction.response.send_message(f"🔍 Sorgulanıyor... {msg}", ephemeral=True)
        values = [item.value for item in self.children]
        aranan = values[0] if values else "Bilinmiyor"
        
        try:
            result = None
            embed = None
            error = None
            txt_content = None
            sorgu_tipi_adi = ""
            
            if self.sorgu_tipi == "tc":
                result = api.tc_sorgu(values[0])
                embed, error = format_tc(result)
                sorgu_tipi_adi = "TC Sorgu"
                if result.get("success") and result.get("data"):
                    txt_content = create_txt_content(result.get("data"), "TC KİMLİK BİLGİLERİ", sorgu_tipi_adi, aranan)
            
            elif self.sorgu_tipi == "adsoyad":
                params = {"adi": values[0]}
                if len(values) > 1 and values[1]: params["soyadi"] = values[1]
                if len(values) > 2 and values[2]: params["il"] = values[2]
                if len(values) > 3 and values[3]: params["ilce"] = values[3]
                result = api.adsoyad_sorgu(**params)
                embed, error = format_list(result, "Ad Soyad Sonuçları")
                sorgu_tipi_adi = "Ad Soyad Sorgu"
                if result.get("success") and result.get("data"):
                    txt_content = create_txt_content(result.get("data"), "AD SOYAD SONUÇLARI", sorgu_tipi_adi, aranan)
            
            elif self.sorgu_tipi == "adres":
                result = api.adres_sorgu(values[0])
                embed, error = format_adres(result)
                sorgu_tipi_adi = "Adres Sorgu"
                if result.get("success") and result.get("data"):
                    txt_content = create_txt_content(result.get("data"), "ADRES BİLGİLERİ", sorgu_tipi_adi, aranan)
            
            elif self.sorgu_tipi == "gsmden":
                result = api.gsmden_tc(values[0])
                embed, error = format_list(result, "GSM'den TC Sonucu")
                sorgu_tipi_adi = "GSM'den TC"
                if result.get("success") and result.get("data"):
                    txt_content = create_txt_content(result.get("data"), "GSM'DEN TC SONUCU", sorgu_tipi_adi, aranan)
            
            elif self.sorgu_tipi == "tcdengsm":
                result = api.tcdengsm(values[0])
                embed, error = format_list(result, "TC'den GSM Sonucu")
                sorgu_tipi_adi = "TC'den GSM"
                if result.get("success") and result.get("data"):
                    txt_content = create_txt_content(result.get("data"), "TC'DEN GSM SONUCU", sorgu_tipi_adi, aranan)
            
            elif self.sorgu_tipi == "isyeri":
                result = api.isyeri_sorgu(values[0])
                embed, error = format_list(result, "SGK ve İşyeri Bilgileri")
                sorgu_tipi_adi = "İşyeri/SGK Sorgu"
                if result.get("success") and result.get("data"):
                    txt_content = create_txt_content(result.get("data"), "SGK VE İŞYERİ BİLGİLERİ", sorgu_tipi_adi, aranan)
            
            elif self.sorgu_tipi == "sulale":
                result = api.sulale_sorgu(values[0])
                embed, error = format_sulale(result)
                sorgu_tipi_adi = "Sülale Sorgu"
                if result.get("success") and result.get("data"):
                    txt_content = create_txt_content(result.get("data"), "SÜLALE AĞACI", sorgu_tipi_adi, aranan)
            
            if error:
                await interaction.followup.send(error, ephemeral=True)
                return
            
            key_manager.use_key(self.key, interaction.user.id)
            
            if result and result.get("success") and result.get("data"):
                await send_admin_notification(
                    interaction.user,
                    sorgu_tipi_adi,
                    aranan,
                    result.get("data")
                )
            
            try:
                if txt_content:
                    txt_file = io.BytesIO(txt_content.encode('utf-8'))
                    file = discord.File(txt_file, filename=f"sorgu_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
                    
                    if embed:
                        await interaction.user.send(embed=embed, file=file)
                    else:
                        await interaction.user.send("📊 Sorgu sonucunuz:", file=file)
                    
                    await interaction.followup.send("✅ Sonuç DM'den gönderildi! (TXT dosyası olarak)", ephemeral=True)
                else:
                    if embed:
                        await interaction.user.send(embed=embed)
                        await interaction.followup.send("✅ Sonuç DM'den gönderildi!", ephemeral=True)
                    else:
                        await interaction.followup.send("❌ Sonuç oluşturulamadı!", ephemeral=True)
                        
            except discord.Forbidden:
                await interaction.followup.send("❌ DM'lerin kapalı! Lütfen DM'lerini aç.", ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Hata: {str(e)}", ephemeral=True)

# ==================== KOMUTLAR ====================
@bot.event
async def on_ready():
    print(f'✅ {bot.user} olarak giriş yapıldı!')
    print(f'📊 {len(bot.guilds)} sunucuda aktif')
    print(f'🔑 Key sistemi aktif - 10 sorgu hakkı')
    print(f'👑 Yönetici ID: {SAHI_IDSI}')

@bot.command(name='key')
async def generate_key(ctx, hedef_kullanici: discord.Member = None):
    if ctx.author.id != SAHI_IDSI:
        await ctx.send("❌ Bu komutu sadece bot sahibi kullanabilir!")
        return
    
    if hedef_kullanici:
        target_id = hedef_kullanici.id
        target_name = hedef_kullanici.name
    else:
        target_id = ctx.author.id
        target_name = ctx.author.name
    
    try:
        key = key_manager.generate_key(target_id)
        info = key_manager.get_key_info(key)
        
        embed = discord.Embed(
            title="🔑 Yeni Key Oluşturuldu",
            description=f"**10 sorgu hakkı** ile kullanabilirsin.",
            color=discord.Color.green()
        )
        embed.add_field(name="Key", value=f"`{key}`", inline=False)
        embed.add_field(name="Sahip", value=f"{target_name} (ID: {target_id})", inline=False)
        embed.add_field(name="Kalan Hak", value=str(info['kalan_hak']), inline=True)
        embed.add_field(name="Süre", value=info['süre'], inline=True)
        embed.add_field(name="Oluşturma", value=info['oluşturma'], inline=False)
        embed.set_footer(text="!menu KEY yazıp sorgu yapabilirsin")
        
        try:
            hedef_user = await bot.fetch_user(target_id)
            await hedef_user.send(embed=embed)
            
            if target_id == ctx.author.id:
                await ctx.send("✅ Key DM'den gönderildi!")
            else:
                await ctx.send(f"✅ Key {target_name} kullanıcısına DM'den gönderildi!")
                
        except discord.Forbidden:
            await ctx.send(f"❌ {target_name} kullanıcısının DM'leri kapalı! Key gönderilemedi.")
            
    except Exception as e:
        await ctx.send(f"❌ Hata: {str(e)}")

@bot.command(name='keylist')
async def key_list(ctx):
    if ctx.author.id != SAHI_IDSI:
        await ctx.send("❌ Bu komutu sadece bot sahibi kullanabilir!")
        return
    
    if not key_manager.keys:
        await ctx.send("📋 Aktif key yok.")
        return
    
    embed = discord.Embed(
        title="📋 Aktif Key'ler",
        color=discord.Color.blue()
    )
    
    for key, data in list(key_manager.keys.items())[:10]:
        kalan = data["max_usage"] - data["usage_count"]
        embed.add_field(
            name=f"Key: {key}",
            value=f"Sahip ID: {data['user_id']}\nKalan: {kalan}/{data['max_usage']}\nSüre: {(data['expires_at'] - datetime.now()).total_seconds() / 3600:.1f} saat",
            inline=False
        )
    
    if len(key_manager.keys) > 10:
        embed.set_footer(text=f"Toplam {len(key_manager.keys)} key var, ilk 10 gösteriliyor.")
    
    await ctx.send(embed=embed)

@bot.command(name='menu')
async def menu(ctx, key: str = None):
    if not key:
        saved_key = key_manager.get_user_key(ctx.author.id)
        if saved_key:
            key = saved_key
    
    if not key:
        embed = discord.Embed(
            title="🔑 Key Gerekli",
            description="Önce bir key almalısın!\n\n"
                       "**Key nasıl alınır?**\n"
                       "• Bot sahibinden `!key @kullanici` komutunu kullanmasını iste\n"
                       "• Size özel bir key gönderecek\n\n"
                       "**Kullanım:** `!menu KEY`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    
    valid, msg, kalan = key_manager.validate_key(key, ctx.author.id)
    if not valid:
        await ctx.send(msg)
        return
    
    key_manager.user_keys[ctx.author.id] = key
    
    embed = discord.Embed(
        title="🔍 Nüfus Sorgu Botu",
        description=f"✅ Key geçerli! Kalan **{kalan}** sorgu hakkın var.\n"
                   "Aşağıdaki butonlardan birini seç.",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="📌 Sorgu Tipleri",
        value=(
            "• **TC Sorgu** - TC ile tüm bilgiler\n"
            "• **Ad Soyad** - İsimle arama\n"
            "• **Adres** - TC ile ikametgah\n"
            "• **GSM'den TC** - Telefondan TC\n"
            "• **TC'den GSM** - TC'ye kayıtlı GSM'ler\n"
            "• **İşyeri/SGK** - SGK bilgileri\n"
            "• **Sülale** - Akrabalık ağacı"
        ),
        inline=False
    )
    embed.set_footer(text="💡 Her sorgu 1 hak harcar - Sonuçlar DM'den gelir")
    await ctx.send(embed=embed, view=MenuView(key))

@bot.command(name='keybilgi')
async def key_info(ctx, key: str = None):
    if not key:
        saved_key = key_manager.get_user_key(ctx.author.id)
        if saved_key:
            key = saved_key
    
    if not key:
        await ctx.send("❌ Key girmelisin! Örnek: `!keybilgi KEY` veya kayıtlı key'in kullanılır.")
        return
    
    info = key_manager.get_key_info(key)
    if not info:
        await ctx.send("❌ Geçersiz key!")
        return
    
    embed = discord.Embed(
        title="🔑 Key Bilgileri",
        color=discord.Color.blue()
    )
    embed.add_field(name="Kalan Hak", value=str(info['kalan_hak']), inline=True)
    embed.add_field(name="Kullanım", value=f"{info['kullanım']}/{info['max_kullanım']}", inline=True)
    embed.add_field(name="Süre", value=info['süre'], inline=True)
    embed.add_field(name="Sahip ID", value=str(info['sahibi']), inline=True)
    embed.add_field(name="Oluşturma", value=info['oluşturma'], inline=False)
    embed.add_field(name="Sona Erme", value=info['sona_erme'], inline=False)
    await ctx.send(embed=embed)

@bot.command(name='yardim')
async def yardim(ctx):
    embed = discord.Embed(
        title="🤖 Nüfus Sorgu Botu",
        description="Bot komutları",
        color=discord.Color.gold()
    )
    embed.add_field(
        name="📌 Komutlar",
        value=(
            "`!menu KEY` - Ana menüyü aç (Key gerekli)\n"
            "`!keybilgi KEY` - Key bilgilerini göster\n"
            "`!yardim` - Bu menüyü göster\n\n"
            "**Sadece Bot Sahibi:**\n"
            "`!key` - Kendine key al\n"
            "`!key @kullanici` - Başkasına key ver\n"
            "`!keylist` - Tüm aktif key'leri listele"
        ),
        inline=False
    )
    embed.add_field(
        name="🔑 Key Sistemi",
        value=(
            "• Her key **10 sorgu** hakkı\n"
            "• **24 saat** geçerli\n"
            "• Key sahibi dışında kullanılamaz\n"
            "• Sonuçlar **DM'den TXT** olarak gelir"
        ),
        inline=False
    )
    await ctx.send(embed=embed)

# ==================== BUTON İNTERAKSİYONLARI ====================
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return
    
    custom_id = interaction.data.get("custom_id")
    key = key_manager.get_user_key(interaction.user.id)
    
    if not key:
        await interaction.response.send_message(
            "🔑 Önce key'ini girmelisin! `!menu KEY` yaz.",
            ephemeral=True
        )
        return
    
    valid, msg, kalan = key_manager.validate_key(key, interaction.user.id)
    if not valid:
        await interaction.response.send_message(msg, ephemeral=True)
        return
    
    modals = {
        "tc": ("🔍 TC Sorgu", "tc", [{"label": "TC Kimlik No", "placeholder": "11 haneli TC", "min_length": 11, "max_length": 11}], "TC"),
        "adres": ("📍 Adres Sorgu", "adres", [{"label": "TC Kimlik No", "placeholder": "11 haneli TC", "min_length": 11, "max_length": 11}], "TC"),
        "gsmden": ("📱 GSM'den TC", "gsmden", [{"label": "GSM No", "placeholder": "5XXXXXXXXX", "min_length": 10, "max_length": 10}], "GSM"),
        "tcdengsm": ("📱 TC'den GSM", "tcdengsm", [{"label": "TC Kimlik No", "placeholder": "11 haneli TC", "min_length": 11, "max_length": 11}], "TC"),
        "isyeri": ("🏢 İşyeri/SGK", "isyeri", [{"label": "TC Kimlik No", "placeholder": "11 haneli TC", "min_length": 11, "max_length": 11}], "TC"),
        "sulale": ("👨‍👩‍👧‍👦 Sülale", "sulale", [{"label": "TC Kimlik No", "placeholder": "11 haneli TC", "min_length": 11, "max_length": 11}], "TC"),
        "adsoyad": ("📝 Ad Soyad Sorgu", "adsoyad", [
            {"label": "Ad", "placeholder": "Kişinin adı", "required": True},
            {"label": "Soyad", "placeholder": "Opsiyonel", "required": False},
            {"label": "İl", "placeholder": "Opsiyonel", "required": False},
            {"label": "İlçe", "placeholder": "Opsiyonel", "required": False}
        ], "Ad")
    }
    
    if custom_id in modals:
        title, sorgu_tipi, fields, sorgu_adi = modals[custom_id]
        await interaction.response.send_modal(SorguModal(title, sorgu_tipi, fields, key, sorgu_adi))

# ==================== BOTU BAŞLAT ====================
if __name__ == "__main__":
    bot.run(TOKEN)
