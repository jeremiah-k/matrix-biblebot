# Troubleshooting Guide

Common issues and solutions for Matrix BibleBot.

## Authentication Issues

### "No credentials found" Error

**Problem:** Bot fails to start with "No credentials found" message.

**Solution:**

```bash
biblebot auth login
```

**Details:**

- The bot requires proper authentication before running
- Legacy access tokens are deprecated and don't support E2EE
- Use the modern authentication flow for best security

### Login Fails with "Invalid credentials"

**Problem:** `biblebot auth login` fails with authentication error.

**Solutions:**

1. **Check username format:**
   - Use full MXID: `@username:homeserver.com`
   - Or just username: `username` (homeserver will be auto-detected)

2. **Verify homeserver URL:**
   - Include protocol: `https://matrix.example.com`
   - Check for typos in domain name

3. **Check password:**
   - Ensure correct password
   - Some servers require app-specific passwords

4. **Server connectivity:**
   ```bash
   curl -I https://your-homeserver.com
   ```

### "Server discovery failed"

**Problem:** Bot can't find Matrix homeserver.

**Solutions:**

1. **Specify full homeserver URL:**

   ```bash
   biblebot auth login --homeserver https://matrix.example.com
   ```

2. **Check DNS/connectivity:**

   ```bash
   nslookup your-homeserver.com
   ping your-homeserver.com
   ```

3. **Verify server supports discovery:**
   ```bash
   curl https://your-homeserver.com/.well-known/matrix/client
   ```

## Configuration Issues

### Bot Doesn't Respond to Messages

**Problem:** Bot is online but doesn't respond to Bible references.

**Solutions:**

1. **Check room configuration:**

   ```bash
   biblebot config check
   ```

   Verify room IDs are correct in config.yaml

2. **Ensure bot is invited:**
   - Bot must be invited to rooms listed in config
   - Check bot is actually in the room (not just invited)

3. **Check message format:**
   - Try exact format: `John 3:16`
   - Ensure no extra characters or formatting

4. **Verify bot permissions:**
   - Bot needs permission to send messages
   - Check room power levels

### "Could not resolve alias" Warning

**Problem:** Bot warns about unresolvable room aliases.

**Solutions:**

1. **Use room IDs instead:**

   ```yaml
   matrix:
     room_ids:
       - "!AbCdEfGhIjKlMnOpQr:matrix.example.com" # Use this
       # - "#room-alias:matrix.example.com"        # Instead of this
   ```

2. **Check alias exists:**
   - Verify alias is published
   - Try joining the alias manually in your client

3. **Check permissions:**
   - Bot needs permission to resolve aliases
   - Some servers restrict alias resolution

### Configuration File Not Found

**Problem:** Bot can't find configuration file.

**Solutions:**

1. **Generate configuration:**

   ```bash
   biblebot config generate
   ```

2. **Check file location:**
   - Default: `~/.config/matrix-biblebot/config.yaml`
   - Specify custom path: `biblebot --config /path/to/config.yaml`

3. **Check file permissions:**
   ```bash
   ls -la ~/.config/matrix-biblebot/
   ```

## End-to-End Encryption Issues

### E2EE Dependencies Missing

**Problem:** "E2EE dependencies not found" warning.

**Solution:**

```bash
pipx install 'matrix-biblebot[e2e]'
# or
pip install 'matrix-biblebot[e2e]'
```

### Bot Can't Decrypt Messages

**Problem:** Bot receives encrypted messages but can't decrypt them.

**Solutions:**

1. **Verify E2EE is enabled:**

   ```yaml
   matrix:
     e2ee:
       enabled: true
   ```

2. **Check device verification:**
   - Verify bot's device in your Matrix client
   - Look for unverified device warnings

3. **Reset E2EE store (last resort):**
   ```bash
   biblebot auth logout  # This removes E2EE store
   biblebot auth login   # Re-login and re-verify
   ```

### "E2EE not supported on Windows"

**Problem:** E2EE fails on Windows systems.

**Explanation:**

- E2EE requires `python-olm` library
- `python-olm` has limited Windows support
- This is a known limitation

**Workarounds:**

1. **Use without E2EE:**

   ```yaml
   matrix:
     e2ee:
       enabled: false
   ```

2. **Use WSL (Windows Subsystem for Linux):**
   - Install bot in WSL environment
   - Full E2EE support available

3. **Use Docker:**
   - Run bot in Linux container
   - Mount config directory for persistence

## API and Network Issues

### "Passage not found" Errors

**Problem:** Bot reports "passage not found" for valid references.

**Solutions:**

1. **Check reference format:**
   - Valid: `John 3:16`, `1 Cor 15:1-4`, `Psalm 23`
   - Invalid: `John 3:99`, `NotABook 1:1`

2. **Try different translation:**
   - KJV: `John 3:16`
   - ESV: `John 3:16 esv`

3. **Check API connectivity:**
   ```bash
   curl "https://bible-api.com/john%203:16?translation=kjv"
   ```

### ESV API Issues

**Problem:** ESV translation not working.

**Solutions:**

1. **Check API key:**

   ```bash
   biblebot config check
   ```

   Should show "ESV API key: Found"

2. **Verify API key:**

   ```bash
   curl -H "Authorization: Token YOUR_API_KEY" \
        "https://api.esv.org/v3/passage/text/?q=John+3:16"
   ```

3. **Get new API key:**
   - Visit [api.esv.org](https://api.esv.org/)
   - Register for free API key
   - Add to config or environment variable

### Network Timeout Issues

**Problem:** Bot times out connecting to APIs or Matrix.

**Solutions:**

1. **Check internet connectivity:**

   ```bash
   ping google.com
   ping matrix.org
   ```

2. **Check firewall/proxy:**
   - Ensure HTTPS (443) is allowed
   - Configure proxy if needed

3. **Increase timeout (if running from source):**
   - Edit timeout values in constants files
   - Rebuild and reinstall

## Performance Issues

### Bot Responds Slowly

**Problem:** Long delays between request and response.

**Solutions:**

1. **Enable caching:**

   ```yaml
   bot:
     cache_enabled: true
   ```

2. **Check system resources:**

   ```bash
   top
   free -h
   ```

3. **Check network latency:**
   ```bash
   ping your-homeserver.com
   ```

### High Memory Usage

**Problem:** Bot uses excessive memory over time.

**Solutions:**

1. **Restart bot periodically:**

   ```bash
   systemctl --user restart biblebot.service
   ```

2. **Check for memory leaks:**
   - Monitor memory usage over time
   - Report if consistently increasing

3. **Reduce cache size (if running from source):**
   - Modify cache settings in configuration

## Service Management Issues

### Systemd Service Won't Start

**Problem:** `systemctl --user start biblebot.service` fails.

**Solutions:**

1. **Check service status:**

   ```bash
   systemctl --user status biblebot.service
   ```

2. **Check service logs:**

   ```bash
   journalctl --user -u biblebot.service -f
   ```

3. **Verify installation:**

   ```bash
   biblebot service install
   ```

4. **Check file permissions:**
   ```bash
   ls -la ~/.config/systemd/user/biblebot.service
   ```

### Service Starts but Bot Doesn't Work

**Problem:** Service shows as running but bot doesn't respond.

**Solutions:**

1. **Check service logs:**

   ```bash
   journalctl --user -u biblebot.service --since "1 hour ago"
   ```

2. **Test manual startup:**

   ```bash
   systemctl --user stop biblebot.service
   biblebot --log-level debug
   ```

3. **Check configuration in service context:**
   - Service runs with different environment
   - Ensure config paths are absolute

## Getting Help

### Enable Debug Logging

For detailed troubleshooting information:

```bash
biblebot --log-level debug
```

### Check System Information

```bash
biblebot auth status  # Shows auth and E2EE status
biblebot config check # Validates configuration
```

### Collect Information for Bug Reports

When reporting issues, include:

1. **Bot version:**

   ```bash
   biblebot --version
   ```

2. **System information:**

   ```bash
   python --version
   uname -a  # Linux/macOS
   ```

3. **Configuration (sanitized):**

   ```bash
   biblebot config check
   ```

4. **Error logs:**

   ```bash
   biblebot --log-level debug 2>&1 | head -50
   ```

5. **Steps to reproduce the issue**

### Where to Get Help

- **GitHub Issues:** [github.com/jeremiah-k/matrix-biblebot/issues](https://github.com/jeremiah-k/matrix-biblebot/issues)
- **Matrix Room:** Join the support room (if available)
- **Documentation:** Check other docs in this repository

### Before Reporting Bugs

1. **Update to latest version:**

   ```bash
   pipx upgrade matrix-biblebot
   ```

2. **Check existing issues:**
   - Search GitHub issues for similar problems
   - Check if issue is already known/fixed

3. **Try minimal reproduction:**
   - Test with fresh config
   - Isolate the specific problem

4. **Gather debug information:**
   - Enable debug logging
   - Collect relevant error messages
