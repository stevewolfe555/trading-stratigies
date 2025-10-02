<!DOCTYPE html>
<html lang="{{ str_replace('_', '-', app()->getLocale()) }}">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Stock Detail - Trading Platform</title>
    @vite(['resources/css/app.css', 'resources/js/app.js'])
    @livewireStyles
</head>
<body class="bg-gray-100">
    <div class="container mx-auto px-4 py-6">
        @livewire('stock-detail', ['symbol' => request()->route('symbol') ?? 'AAPL'])
    </div>
    @livewireScripts
</body>
</html>
