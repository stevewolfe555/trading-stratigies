<x-app-layout>
    <x-slot name="header">
        <h2 class="font-semibold text-xl text-gray-800 leading-tight">
            {{ __('Account') }}
        </h2>
    </x-slot>

    <div class="py-6">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="bg-white rounded-lg shadow p-6">
                <h1 class="text-2xl font-bold text-gray-900 mb-4">Account & Portfolio</h1>
                
                <div class="space-y-6">
                    <!-- Account Overview -->
                    <div>
                        <h2 class="text-lg font-semibold text-gray-700 mb-3">Account Overview</h2>
                        <div class="grid grid-cols-3 gap-4">
                            <div class="bg-blue-50 p-4 rounded-lg">
                                <div class="text-sm text-gray-600">Portfolio Value</div>
                                <div class="text-2xl font-bold text-blue-600">$100,000.00</div>
                            </div>
                            <div class="bg-green-50 p-4 rounded-lg">
                                <div class="text-sm text-gray-600">Buying Power</div>
                                <div class="text-2xl font-bold text-green-600">$100,000.00</div>
                            </div>
                            <div class="bg-purple-50 p-4 rounded-lg">
                                <div class="text-sm text-gray-600">Cash</div>
                                <div class="text-2xl font-bold text-purple-600">$100,000.00</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</x-app-layout>
