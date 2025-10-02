<!DOCTYPE html>
<html lang="{{ str_replace('_', '-', app()->getLocale()) }}">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Account - Trading Platform</title>
    @vite(['resources/css/app.css', 'resources/js/app.js'])
</head>
<body class="bg-gray-100">
    <!-- Navigation -->
    <nav class="bg-white shadow-sm border-b border-gray-200">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex">
                    <div class="flex-shrink-0 flex items-center">
                        <span class="text-xl font-bold text-gray-900">Trading Platform</span>
                    </div>
                    <div class="hidden sm:ml-6 sm:flex sm:space-x-8">
                        <a href="{{ route('watchlist') }}" class="border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium">
                            📊 Watchlist
                        </a>
                        <a href="{{ route('strategies') }}" class="border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium">
                            ⚙️ Strategies
                        </a>
                        <a href="{{ route('account') }}" class="border-blue-500 text-gray-900 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium">
                            💼 Account
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto py-6 px-4">
        <div class="bg-white rounded-lg shadow p-6">
            <h2 class="text-2xl font-bold text-gray-900 mb-4">💼 Account & Portfolio</h2>
            <p class="text-gray-600">
                Consolidated account view coming soon. This will show:
            </p>
            <ul class="mt-4 space-y-2 text-gray-700">
                <li>• Portfolio summary and performance</li>
                <li>• All open positions across markets</li>
                <li>• Complete trade history</li>
                <li>• P&L charts and analytics</li>
                <li>• Risk metrics and exposure</li>
            </ul>
            <div class="mt-6">
                <a href="{{ route('watchlist') }}" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 inline-block">
                    ← Back to Watchlist
                </a>
            </div>
        </div>
    </main>
</body>
</html>
