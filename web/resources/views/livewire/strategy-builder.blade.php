<div class="space-y-6">
    <h3 class="font-semibold text-lg">Strategy Builder</h3>

    <div class="grid gap-4 sm:grid-cols-4">
        <div class="sm:col-span-2">
            <x-input-label for="name" :value="__('Name')" />
            <x-text-input id="name" type="text" class="mt-1 block w-full" wire:model.defer="name" placeholder="AAPL SMA20 Breakout" />
            <x-input-error :messages="$errors->get('name')" class="mt-2" />
        </div>
        <div>
            <x-input-label for="symbol" :value="__('Symbol')" />
            <select id="symbol" wire:model="symbol" class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500">
                @foreach($this->symbols as $sym)
                    <option value="{{ $sym }}">{{ $sym }}</option>
                @endforeach
            </select>
            <x-input-error :messages="$errors->get('symbol')" class="mt-2" />
        </div>
        <div>
            <x-input-label for="period" :value="__('SMA Period')" />
            <x-text-input id="period" type="number" min="1" class="mt-1 block w-full" wire:model.defer="period" />
            <x-input-error :messages="$errors->get('period')" class="mt-2" />
        </div>
        <div class="flex items-end">
            <label class="inline-flex items-center space-x-2">
                <input type="checkbox" wire:model="active" class="rounded border-gray-300 text-indigo-600 shadow-sm focus:ring-indigo-500">
                <span>Active</span>
            </label>
        </div>
        <div class="sm:col-span-4">
            <x-primary-button wire:click="save">Save Strategy</x-primary-button>
        </div>
    </div>

    <div class="mt-6">
        <h4 class="font-semibold">Existing Strategies</h4>
        <div class="overflow-x-auto mt-2">
            <table class="min-w-full text-sm">
                <thead>
                <tr class="text-left border-b">
                    <th class="py-2 pr-4">Name</th>
                    <th class="py-2 pr-4">Symbol</th>
                    <th class="py-2 pr-4">Type</th>
                    <th class="py-2 pr-4">Period</th>
                    <th class="py-2 pr-4">Active</th>
                    <th class="py-2 pr-4">Actions</th>
                </tr>
                </thead>
                <tbody>
                @forelse($strategies as $s)
                    <tr class="border-b">
                        <td class="py-2 pr-4 font-medium">{{ $s['name'] }}</td>
                        <td class="py-2 pr-4">{{ $s['symbol'] }}</td>
                        <td class="py-2 pr-4">{{ $s['type'] }}</td>
                        <td class="py-2 pr-4">{{ $s['period'] }}</td>
                        <td class="py-2 pr-4">
                            <span class="px-2 py-1 text-xs rounded {{ $s['active'] ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600' }}">
                                {{ $s['active'] ? 'Active' : 'Inactive' }}
                            </span>
                        </td>
                        <td class="py-2 pr-4">
                            <x-secondary-button wire:click="toggle({{ $s['id'] }})">Toggle</x-secondary-button>
                        </td>
                    </tr>
                @empty
                    <tr>
                        <td colspan="6" class="py-4 text-gray-500">No strategies yet.</td>
                    </tr>
                @endforelse
                </tbody>
            </table>
        </div>
    </div>
</div>
