<!DOCTYPE html>
<style>
    @page {
        size: letter;
    }
</style>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: sans-serif; margin: 2em; }
        h1 { font-size: 1.5em; }
        table { border-collapse: collapse; width: 100%; margin-top: 1em; }
        th, td { border: 1px solid #333; padding: 8px; text-align: left; }
        th { background: #eee; }
        td:nth-child(2) { text-align: right; }
        td.page-num .page-link { color: #00f; text-decoration: underline; }
    </style>
</head>
<body>
    <h1>Table of Contents</h1>
    <p>Select your preferred language below. Each link will take you to the complete Instructions for Use (IFU) in that language.</p>
    <hr>
    <br>
    <table>
        <thead><tr><th>Document</th><th>Page</th></tr></thead>
        <tbody>{{table_rows}}</tbody>
    </table>
    <hr>
    <p>Each language section contains a complete and independent version of the IFU. <br>
    All language versions are equivalent in content and differ only by translation.</p>
    <hr>
    <br>
    <p>Document Number: {{doc_number}}<br>
    Document Version: {{doc_version}}</p>
</body>
</html>
