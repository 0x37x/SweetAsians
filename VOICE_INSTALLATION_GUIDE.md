# User Guide for Discord 24/7 Voice-Stay Tool (`voice.py`)

A standalone Python tool that allows your Discord account to log in automatically using a **User Token**, join a specific **Voice Channel ID**, and remain connected to that voice channel 24/7.

---

## 🚀 Key Features

- **Direct Voice Channel ID Entry**: Paste the ID to join the voice channel immediately—no need to manually search through servers.
- **Intuitive Selection Menu**: If you don't know the ID, the script will display a list of your servers and their voice channels, allowing you to select one by number.
- **Automatic Reconnection (Anti-Kick & Anti-AFK)**:
- If the connection drops or you are disconnected by someone else: The script automatically reconnects after 5 seconds. 
- If you are moved to a server's "AFK" channel: The script detects this and automatically moves you back to your chosen voice channel.
- **Self-Mute & Self-Deafen**: Saves bandwidth, prevents audio playback, and displays the "deafened" icon on your Discord profile.
- **Uptime Monitor**: Tracks how long you have been connected (e.g., `01 hours 45 minutes 10 seconds`) and displays your connection ping.
- **Automatic Configuration Saving**: Settings are saved to a `voice_config.json` file, so you don't need to re-enter information the next time you run the tool.

---

## 📋 Step 1: How to Obtain Your Token and Voice Channel ID

### 1. How to Get Your User Token
1. Open Discord in your web browser (Chrome, Edge, Cốc Cốc, Brave, etc.) or via the Discord Desktop application. 2. Press the **F12** key (or `Ctrl + Shift + I`) to open **Developer Tools**.
3. Select the **Console** tab, paste the following code, and press **Enter**:
```javascript
window.webpackChunkdiscord_app.push([
[Math.random()],
{},
(req) => {
for (const m of Object.keys(req.c).map((x) => req.c[x].exports).filter((x) => x)) {
if (m.default && m.default.getToken !== undefined) {
return console.log('%cYOUR TOKEN: ' + m.default.getToken(), 'color: #00ff00; font-size: 16px;');
}
if (m.getToken !== undefined) {
return console.log('%cYOUR TOKEN: ' + m.getToken(), 'color: #00ff00; font-size: 16px;');
}
}
}
]); 
```
4. Copy the Token string that appears (a long sequence of characters).

---

### 2. How to Get a Voice Channel ID
1. In Discord, go to **User Settings** -> **Advanced**.
2. Toggle on **Developer Mode**.
3. Go to the server and find the voice channel you want to use:
- **Right-click** on the voice channel name. 
- Select **Copy Channel ID**. ---

## 💻 Step 2: How to Run the Tool

Open a Terminal or PowerShell window in this directory and use one of the following methods:

### Method 1: Interactive Mode (Recommended)
```bash
python voice.py
```
- The tool will prompt you for the following:
1. **Enter Token**: Paste your account token (or select one from the list if previously saved). 
2. **Enter Voice Channel ID**: Paste the Voice Channel ID you copied earlier. 
3. Choose whether to **Mute** your microphone and **Deafen** your audio (press Enter to enable both by default). 
4. Choose to save your configuration for automatic use next time.

---

### Method 2: Quick Start (Single-line Command)
If you already have your Token and Voice Channel ID, you can run the tool directly without any prompts:
```bash
python voice.py --token "ENTER_TOKEN_HERE" --channel ENTER_VOICE_ID_HERE
```

*Example:*
```bash
python voice.py --token "MTIxOTM4NDc5..." --channel 1259347354423922710
```

---

### Method 3: Changing Voice Channels or Resetting Configuration
If you wish to switch to a different voice channel or change your token:
```bash
python voice.py --setup
```

---

## ⚙️ CLI Options

| Parameter | Description | Example |
| :--- | :--- | :--- |
| `--token` | Provide the account token directly | `--token "MTIz..."` |
| `--channel` | Provide the Voice Channel ID directly | `--channel 123456789012345678` |
| `--mute` | Toggle microphone mute (`true` or `false`) | `--mute true` |
| `--deaf` | Toggle headphone mute (`true` or `false`) | `--deaf true` |
| `--status` | Set the displayed status content | `--status "Listening to chill music"` |
| `--setup` | Re-open the setup interface to re-select the Server/Channel | `--setup` |
| `--help` | View the list of available parameters | `--help` |

---

## 🛑 How to Stop the Voice Session
When you want to exit:
- Press the **`Ctrl + C`** key combination in the command-line window.
- The tool will automatically disconnect safely from the voice channel, display the total duration of your session, and close the application.