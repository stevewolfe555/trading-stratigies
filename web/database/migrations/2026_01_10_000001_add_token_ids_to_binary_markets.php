<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Add YES/NO token IDs to binary_markets table.
     *
     * These are required to map Polymarket WebSocket events (which use token_id)
     * to our markets. Each binary market has exactly two tokens: YES and NO.
     */
    public function up(): void
    {
        Schema::table('binary_markets', function (Blueprint $table) {
            // Polymarket token IDs for YES and NO outcomes
            $table->string('yes_token_id', 100)->nullable()->after('market_id')
                ->comment('Polymarket token ID for YES outcome');
            $table->string('no_token_id', 100)->nullable()->after('yes_token_id')
                ->comment('Polymarket token ID for NO outcome');

            // Add indexes for fast lookups from WebSocket events
            $table->index('yes_token_id', 'idx_binary_markets_yes_token');
            $table->index('no_token_id', 'idx_binary_markets_no_token');
        });
    }

    /**
     * Reverse the migration.
     */
    public function down(): void
    {
        Schema::table('binary_markets', function (Blueprint $table) {
            $table->dropIndex('idx_binary_markets_yes_token');
            $table->dropIndex('idx_binary_markets_no_token');
            $table->dropColumn(['yes_token_id', 'no_token_id']);
        });
    }
};
