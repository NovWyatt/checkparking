<?php

declare(strict_types=1);

/**
 * Kiểm tra nhanh lỗi UTF-8/tiếng Việt thường gặp trong dự án.
 *
 * Cách chạy:
 *   php scripts/check-vietnamese-encoding.php
 *   php scripts/check-vietnamese-encoding.php app resources routes database
 */

$root = dirname(__DIR__);
$targets = array_slice($argv, 1);
if ($targets === []) {
    $targets = ['app', 'resources', 'routes', 'database', 'config', 'public'];
}

$excludeFiles = [
    // Các file rule có chứa ví dụ sai để hướng dẫn Codex, nên bỏ qua khi quét mặc định.
    'AGENTS.md',
    'CODEX_RULES_PROMPT.md',
    'CODEX_TASK_TEMPLATE.md',
    'ENCODING_RULES.md',
    'PROJECT_CONTEXT_TEMPLATE.md',
    '.codex/instructions.md',
    'codex/instructions.md',
    'README.md',
    'scripts/check-vietnamese-encoding.php',
];

$excludeDirs = [
    '.git',
    'vendor',
    'node_modules',
    'storage',
    'bootstrap/cache',
    'public/build',
    'public/vendor',
];

$allowedExtensions = [
    'php',
    'blade.php',
    'js',
    'css',
    'html',
    'htm',
    'md',
    'json',
    'yml',
    'yaml',
    'xml',
    'txt',
    'env',
];

$mojibakePattern = '/(Ã|Â|Ä|Æ|�|á»|áº|â€™|â€œ|â€|Â·|Ä‘|Äƒ|áº¡|áº£|áº¥|áº§|áº©|áº«|áº­|áº¯|áº±|áº³|áºµ|áº·|áº¹|áº»|áº½|áº¿|á»|á»ƒ|á»…|á»‡|á»‰|á»‹|á»|á»|á»‘|á»“|á»•|á»—|á»™|á»›|á»|á»Ÿ|á»¡|á»£|á»¥|á»§|á»©|á»«|á»­|á»¯|á»±|á»³|á»·|á»¹|á»µ)/u';

// Script này cố ý nghiêm với numeric entity vì Codex hay biến tiếng Việt thành dạng này.
$entityPattern = '/(&#\d+;|&#x[0-9a-fA-F]+;|&agrave;|&aacute;|&acirc;|&atilde;|&egrave;|&eacute;|&ecirc;|&igrave;|&iacute;|&ograve;|&oacute;|&ocirc;|&otilde;|&ugrave;|&uacute;|&yacute;|&Agrave;|&Aacute;|&Acirc;|&Atilde;|&Egrave;|&Eacute;|&Ecirc;|&Igrave;|&Iacute;|&Ograve;|&Oacute;|&Ocirc;|&Otilde;|&Ugrave;|&Uacute;|&Yacute;)/';

$teencodePattern = '/\b(ko|k|dc|đc|mk|mn|ae|vs|j|z|hok|khum)\b/ui';

$issues = [];
$checked = 0;

foreach ($targets as $target) {
    $path = resolvePath($root, $target);
    if (!file_exists($path)) {
        continue;
    }

    if (is_file($path)) {
        checkFile($path, $root, $allowedExtensions, $excludeFiles, $mojibakePattern, $entityPattern, $teencodePattern, $issues, $checked);
        continue;
    }

    $iterator = new RecursiveIteratorIterator(
        new RecursiveCallbackFilterIterator(
            new RecursiveDirectoryIterator($path, FilesystemIterator::SKIP_DOTS),
            function (SplFileInfo $file) use ($root, $excludeDirs): bool {
                if (!$file->isDir()) {
                    return true;
                }

                $relative = ltrim(normalizePath(substr($file->getPathname(), strlen($root) + 1)), './');
                foreach ($excludeDirs as $excludeDir) {
                    $excludeDir = trim(normalizePath($excludeDir), '/');
                    if ($relative === $excludeDir || str_starts_with($relative, $excludeDir . '/')) {
                        return false;
                    }
                }

                return true;
            }
        )
    );

    foreach ($iterator as $file) {
        if (!$file instanceof SplFileInfo || !$file->isFile()) {
            continue;
        }

        checkFile($file->getPathname(), $root, $allowedExtensions, $excludeFiles, $mojibakePattern, $entityPattern, $teencodePattern, $issues, $checked);
    }
}

if ($issues === []) {
    echo "OK: Đã kiểm tra {$checked} file, chưa thấy lỗi encoding/tiếng Việt thường gặp.\n";
    exit(0);
}

echo "PHÁT HIỆN LỖI ENCODING/TIẾNG VIỆT:\n\n";
foreach ($issues as $issue) {
    echo "- {$issue}\n";
}

echo "\nTổng file đã kiểm tra: {$checked}\n";
echo "Tổng lỗi: " . count($issues) . "\n";
exit(1);

function resolvePath(string $root, string $target): string
{
    if (preg_match('#^[A-Za-z]:[\\\/]#', $target) || str_starts_with($target, '/')) {
        return $target;
    }

    return $root . DIRECTORY_SEPARATOR . $target;
}

function normalizePath(string $path): string
{
    return str_replace('\\', '/', $path);
}

function hasAllowedExtension(string $path, array $allowedExtensions): bool
{
    $normalized = strtolower(normalizePath($path));

    foreach ($allowedExtensions as $extension) {
        $extension = strtolower($extension);
        if (str_ends_with($normalized, '.' . $extension)) {
            return true;
        }
    }

    return false;
}

function checkFile(
    string $path,
    string $root,
    array $allowedExtensions,
    array $excludeFiles,
    string $mojibakePattern,
    string $entityPattern,
    string $teencodePattern,
    array &$issues,
    int &$checked
): void {
    $relative = ltrim(normalizePath(substr($path, strlen($root) + 1)), './');

    if (in_array($relative, $excludeFiles, true)) {
        return;
    }

    if (!hasAllowedExtension($path, $allowedExtensions)) {
        return;
    }
    $content = @file_get_contents($path);
    if ($content === false) {
        $issues[] = "{$relative}: không đọc được file";
        return;
    }

    $checked++;

    if (str_starts_with($content, "\xEF\xBB\xBF")) {
        $issues[] = "{$relative}: có UTF-8 BOM, nên lưu UTF-8 không BOM";
    }

    if ($content !== '' && preg_match('//u', $content) !== 1) {
        $issues[] = "{$relative}: file không phải UTF-8 hợp lệ";
        return;
    }

    $lines = preg_split('/\R/u', $content);
    if ($lines === false) {
        $issues[] = "{$relative}: không tách dòng được";
        return;
    }

    foreach ($lines as $index => $line) {
        $lineNumber = $index + 1;

        if (preg_match($mojibakePattern, $line, $match) === 1) {
            $issues[] = "{$relative}:{$lineNumber}: nghi mojibake `{$match[0]}` | " . trimForReport($line);
        }

        if (preg_match($entityPattern, $line, $match) === 1) {
            $issues[] = "{$relative}:{$lineNumber}: nghi HTML entity cho tiếng Việt `{$match[0]}` | " . trimForReport($line);
        }

        if (preg_match($teencodePattern, $line, $match) === 1) {
            $issues[] = "{$relative}:{$lineNumber}: nghi teencode `{$match[0]}` | " . trimForReport($line);
        }
    }
}

function trimForReport(string $line): string
{
    $line = trim($line);
    $line = preg_replace('/\s+/u', ' ', $line) ?? $line;

    if (function_exists('mb_strlen') && function_exists('mb_substr')) {
        return mb_strlen($line) > 160 ? mb_substr($line, 0, 157) . '...' : $line;
    }

    return strlen($line) > 160 ? substr($line, 0, 157) . '...' : $line;
}
